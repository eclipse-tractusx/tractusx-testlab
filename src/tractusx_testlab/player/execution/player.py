#################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""TestlabPlayer — async executor that runs TCKs test-by-test, step-by-step."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from tractusx_testlab.authoring.test import Tck as Tck
from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure.profiles import InfrastructureManager
from tractusx_testlab.logging import transcript
from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models import TckResult as TckResult  # SDK alias
from tractusx_testlab.player.execution._binding import bind_infrastructure
from tractusx_testlab.player.execution._context_seeder import require_inputs, seed_context_variables
from tractusx_testlab.player.execution._skip import resolve_skip_ids
from tractusx_testlab.player.execution._trace_formatter import open_run_records
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.infrastructure_seeder import seed_infrastructure_services
from tractusx_testlab.player.execution.mock_server import _BackgroundMockServer
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.execution.session import TckSession
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.player.loading._encrypted import engine_package_keys
from tractusx_testlab.player.loading._parser import is_encrypted_package
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import get_callback_manager, set_callback_manager
from tractusx_testlab.services.instances import ServiceManager


class TestlabPlayer:
    """High-level API for executing test cases.

    Usage::

        player = TestlabPlayer()
        result = await player.run("my_tck.tck")

    An adopter embedding the player states the deployment it runs against by
    handing over an :class:`InfrastructureManager` — the engine's own connector,
    registry and submodel server, and the system under test::

        player = TestlabPlayer(infrastructure=InfrastructureManager(integration))

    A host that lets a person drive the run test by test (labs, ``async: true``
    tests) opens a :class:`TckSession` with :meth:`open_session` instead.
    """

    __slots__ = (
        "_config",
        "_infrastructure",
        "_jobs",
        "_loader",
        "_logger",
        "_mock_server",
        "_monitor",
    )

    def __init__(
        self,
        config: TestlabConfig | None = None,
        infrastructure: InfrastructureManager | None = None,
    ) -> None:
        """Build a player for *config*, running against *infrastructure*.

        Both are resolved from the engine's own configuration when omitted, so
        an embedder supplies whichever half it decides and inherits the other
        from the config file and the environment.
        """
        self._config = config or ConfigLoader.load()
        self._infrastructure = infrastructure or InfrastructureManager.from_config(self._config)
        self._logger = StructuredLogger("testlab.player", logs_dir=self._config.logs_dir)
        self._monitor = ExecutionMonitor(self._logger)
        self._jobs = JobManager()
        self._loader = Loader()
        self._mock_server: _BackgroundMockServer | None = None

    @property
    def infrastructure(self) -> InfrastructureManager:
        """The deployments this player can run against."""
        return self._infrastructure

    @property
    def jobs(self) -> JobManager:
        return self._jobs

    @property
    def monitor(self) -> ExecutionMonitor:
        return self._monitor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        path: str | Path,
        runtime_vars: dict | None = None,
        job_id: str | None = None,
    ) -> TckResult:
        """Verify and execute the ``.tck`` package at *path* — packages only."""
        resolved = Path(path)
        encrypted = is_encrypted_package(resolved)
        self._monitor.on_package_verify_start(resolved.name, encrypted=encrypted)
        try:
            keys = self._package_keys(resolved) if encrypted else {}
            tck = self._loader.load(resolved, **keys)
        except ValueError as exc:
            self._monitor.on_package_verify_failed(resolved.name, str(exc))
            raise
        self._monitor.on_package_verify_passed(resolved.name, checksum="")
        return await self.run_tck(tck, runtime_vars=runtime_vars, job_id=job_id)

    def _package_keys(self, package: Path) -> dict[str, bytes]:
        """Resolve the keys an encrypted *package* needs from this engine's config."""
        return engine_package_keys(self._config, package)

    async def run_tck(
        self,
        tck: Tck,
        runtime_vars: dict | None = None,
        job_id: str | None = None,
    ) -> TckResult:
        """Execute a loaded Tck object.

        Every test runs in manifest order, ``async: true`` ones included: a run
        nobody drives leaves nothing for anyone to ask for.

        Args:
            tck: The TCK to execute.
            runtime_vars: Optional runtime variable overrides.
            job_id: Reuse the job with this id, or create one under it. The
                server hands over a job it already queued; the CLI hands over an
                id it committed to when it opened the transcript, before there
                was a TCK to make a job from.
        """
        session = await self.open_session(tck, runtime_vars=runtime_vars, job_id=job_id)
        try:
            await session.run_all()
        finally:
            result = await session.close()
        return result

    async def open_session(
        self,
        tck: Tck,
        runtime_vars: dict | None = None,
        job_id: str | None = None,
    ) -> TckSession:
        """Start a run of *tck* and hold it open until the session is closed.

        Everything a run does before its first test is done here; the tests run
        when the session is asked to run them (:class:`TckSession`). A run refused
        before it started (a missing input, an unbindable infrastructure) raises,
        with the job failed and nothing left open.
        """
        job = self._jobs.get(job_id) if job_id else None
        if job is None:
            job = self._jobs.create(tck.id, job_id=job_id)
        if runtime_vars:
            job.runtime_vars = runtime_vars

        records = contextlib.ExitStack()
        # A CLI run opened its transcript before it had a TCK to compile, so
        # that the compiler's output is in it too; this is a no-op there and the
        # only transcript there is for a server or an embedder.
        records.enter_context(
            transcript.recording(transcript.transcript_path(self._config.logs_dir, job.job_id))
        )
        try:
            return self._open_session(tck, job, runtime_vars, records)
        except BaseException:
            records.close()
            raise

    def _open_session(
        self, tck: Tck, job: Any, runtime_vars: dict | None, records: contextlib.ExitStack
    ) -> TckSession:
        """Prepare everything the tests of *tck* need, for an already-created job."""
        self._jobs.start(job.job_id)

        job_logger, trace = open_run_records(self._logger, self._config, tck.id, job.job_id)
        monitor = self._create_job_monitor(job_logger, trace)
        monitor.on_job_started(job.job_id, tck.id)

        svc_mgr = ServiceManager()
        context = StepContext(
            services=svc_mgr,
            job=job,
            config=self._config,
            infrastructure=self._infrastructure.active,
        )

        context.hold.bind(self._jobs, job.job_id, monitor)
        seed_context_variables(context, tck, runtime_vars)

        # Before the callback server: a run this engine cannot reach, or was
        # never given its inputs, is refused before anything has started.
        try:
            require_inputs(context, tck)
            bind_infrastructure(self._infrastructure, context, tck)
        except Exception as exc:
            self._jobs.fail(job.job_id, str(exc))
            raise

        skip_ids = resolve_skip_ids(tck, runtime_vars)
        self._ensure_callback_manager()
        seed_infrastructure_services(svc_mgr, context)

        return TckSession(
            tck=tck,
            job=job,
            context=context,
            monitor=monitor,
            jobs=self._jobs,
            services=svc_mgr,
            job_logger=job_logger,
            trace=trace,
            skip_ids=skip_ids,
            records=records,
            on_close=self._stop_mock_server,
        )

    # ------------------------------------------------------------------
    # TCK helpers
    # ------------------------------------------------------------------

    def _create_job_monitor(
        self, job_logger: StructuredLogger, trace: ExecutionTrace | None = None
    ) -> ExecutionMonitor:
        """Create a monitor for a job, dynamically forwarding to player-level callbacks."""
        monitor = ExecutionMonitor(job_logger, trace)

        def _forward_to_player(event: str, payload: dict) -> None:
            """Forward events to all current player-level callbacks (dynamic lookup)."""
            for cb in self._monitor._callbacks:
                with contextlib.suppress(RuntimeError, TypeError, ValueError):
                    cb(event, payload)

        monitor.add_callback(_forward_to_player)
        return monitor

    def _ensure_callback_manager(self) -> None:
        """Ensure a CallbackManager and mock server exist for callback steps."""
        if get_callback_manager() is not None:
            return
        manager = CallbackManager()
        set_callback_manager(manager)
        self._mock_server = _BackgroundMockServer(
            port=self._config.server_port,
            config=self._config,
        )
        self._mock_server.start()

    def _stop_mock_server(self) -> None:
        """Stop the mock server this player started for the run, if it started one."""
        if self._mock_server is not None:
            self._mock_server.stop()
            self._mock_server = None

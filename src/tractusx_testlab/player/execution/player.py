#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""TestlabPlayer — async executor that runs TCKs script-by-script, step-by-step."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure.manager import InfrastructureManager
from tractusx_testlab.infrastructure.mapping import collect_overrides, flatten
from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.player.execution.infrastructure_seeder import seed_infrastructure_services
from tractusx_testlab.models import (
    JobStatus,
    ScriptResult,
    ScriptStatus,
    TckResult as TckResult,  # SDK alias
)
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.execution.mock_server import _BackgroundMockServer
from tractusx_testlab.player.execution.step_runner import (
    execute_teardown_steps,
    execute_main_steps,
    execute_setup_steps,
    run_script,
)
from tractusx_testlab.player.execution._trace_formatter import (
    build_tck_result,
    finalize_job,
    make_intentionally_skipped_result,
    make_skipped_result,
)
from tractusx_testlab.player.execution._skip import resolve_skip_ids
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.player.loading.ordering import topological_sort
from tractusx_testlab.scripting._infrastructure import collect_infrastructure_requirements
from tractusx_testlab.scripting.script import Tck as Tck, TestScript
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import get_callback_manager, set_callback_manager
from tractusx_testlab.services.manager import ServiceManager
from tractusx_testlab.syntax import defaults

# Ensure built-in steps are registered
import tractusx_testlab.steps  # noqa: F401


class TestlabPlayer:
    """High-level API for executing test cases.

    Usage::

        player = TestlabPlayer()
        result = await player.run("my_tck.yaml")

    An adopter embedding the player states the deployment it runs against by
    handing over an :class:`InfrastructureManager` — the engine's own connector,
    registry and submodel server, and the system under test::

        player = TestlabPlayer(infrastructure=InfrastructureManager(integration))
    """

    __slots__ = (
        "_config", "_logger", "_monitor", "_jobs", "_loader", "_mock_server", "_infrastructure",
    )

    def __init__(
        self,
        config: Optional[TestlabConfig] = None,
        infrastructure: Optional[InfrastructureManager] = None,
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
        self._mock_server: Optional[_BackgroundMockServer] = None

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

    async def run(self, path: str | Path, runtime_vars: Optional[dict] = None) -> TckResult:
        """Load and execute a TCK, emitting package verification events before execution."""
        resolved = Path(path)
        import zipfile as _zf
        encrypted = _zf.is_zipfile(resolved) and _is_encrypted_tck(resolved)
        self._monitor.on_package_verify_start(resolved.name, encrypted=encrypted)
        try:
            tck = self._loader.load(resolved)
        except ValueError as exc:
            self._monitor.on_package_verify_failed(resolved.name, str(exc))
            raise
        self._monitor.on_package_verify_passed(resolved.name, checksum="")
        return await self.run_tck(tck, runtime_vars=runtime_vars)

    async def run_tck(
        self,
        tck: Tck,
        runtime_vars: Optional[dict] = None,
        job_id: Optional[str] = None,
    ) -> TckResult:
        """Execute a loaded Tck object.

        Args:
            tck: The TCK to execute.
            runtime_vars: Optional runtime variable overrides.
            job_id: If provided, reuse an existing job instead of creating a new one.
        """
        if job_id:
            job = self._jobs.get(job_id)
            if job is None:
                raise ValueError(f"Job '{job_id}' not found in job manager")
        else:
            job = self._jobs.create(tck.id)
        if runtime_vars:
            job.runtime_vars = runtime_vars

        self._jobs.start(job.job_id)

        job_logger = self._logger.for_job(job.job_id)
        monitor = self._create_job_monitor(job_logger)
        monitor.on_job_started(job.job_id, tck.id)

        svc_mgr = ServiceManager()
        context = StepContext(
            services=svc_mgr,
            job=job,
            config=self._config,
            infrastructure=self._infrastructure.active,
        )

        seed_context_variables(context, tck, runtime_vars)

        # Before the callback server: a run this engine cannot reach is refused
        # without having started anything it would then have to shut down.
        try:
            self._bind_infrastructure(context, tck)
        except Exception as exc:
            self._jobs.fail(job.job_id, str(exc))
            raise

        self._ensure_callback_manager()
        seed_infrastructure_services(svc_mgr, context)

        skip_ids = resolve_skip_ids(tck, runtime_vars)

        tck_started_at = datetime.now(timezone.utc)
        ordered_scripts = topological_sort(tck.scripts)
        script_results = await self._execute_scripts_in_order(
            ordered_scripts, context, job, monitor, skip_ids,
        )
        tck_finished_at = datetime.now(timezone.utc)

        svc_mgr.teardown()

        if self._mock_server is not None:
            self._mock_server.stop()
            self._mock_server = None

        result = build_tck_result(
            tck.name, script_results, tck_started_at, tck_finished_at,
        )
        finalize_job(self._jobs, job, result, monitor, job_logger)
        return result

    # ------------------------------------------------------------------
    # TCK helpers
    # ------------------------------------------------------------------

    def _bind_infrastructure(self, context: StepContext, tck: Tck) -> None:
        """Settle which deployment this run targets, and refuse one it cannot reach.

        The active deployment is the starting point and the run's own variables
        are written over it, so an operator overrides a single address for one
        run — ``--var infrastructure.sut.dtr.base_url=…`` — without touching the
        registered deployment or the next run.

        What the TCK requires is then checked against what is bound, before the
        first step: a capability declared ``required: true`` with nothing behind
        it fails here, naming the key the operator owes, rather than surfacing
        as an empty URL somewhere in the middle of the run.

        What the TCK certifies against — its ecosystem release and its per-
        capability standards — is then carried onto the bindings, so the SDK
        builds Saturn or Jupiter services because the TCK says so and not
        because a config file repeated it.

        The resolved bindings are published back into the variable namespace so
        ``${{ infrastructure.sut.connector.dsp_url }}`` resolves the same
        whether the value came from a profile, the environment, or the CLI.
        """
        requirements = collect_infrastructure_requirements(tck)
        release, release_stated = _target_release(tck)

        resolved = self._infrastructure.resolve(collect_overrides(context.variables))
        self._infrastructure.validate(requirements, resolved)
        resolved = self._infrastructure.align(
            requirements, release, release_stated=release_stated, infrastructure=resolved,
        )

        context.bind_infrastructure(resolved)
        for key, value in flatten(resolved).items():
            context.set_variable(key, value)

    def _create_job_monitor(self, job_logger: StructuredLogger) -> ExecutionMonitor:
        """Create a monitor for a job, dynamically forwarding to player-level callbacks."""
        monitor = ExecutionMonitor(job_logger)

        def _forward_to_player(event: str, payload: dict) -> None:
            """Forward events to all current player-level callbacks (dynamic lookup)."""
            for cb in self._monitor._callbacks:
                try:
                    cb(event, payload)
                except (RuntimeError, TypeError, ValueError):
                    pass

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

    async def _execute_scripts_in_order(
        self,
        ordered_scripts: list[TestScript],
        context: StepContext,
        job: Any,
        monitor: ExecutionMonitor,
        skip_ids: frozenset[str],
    ) -> list[ScriptResult]:
        """Execute scripts respecting dependency order, skipping on unmet deps."""
        script_results: list[ScriptResult] = []
        completed_tests: set[str] = set()

        for idx, script in enumerate(ordered_scripts):
            # 1. Intentional skip requested by the operator.
            if script.test_id in skip_ids:
                skipped = make_intentionally_skipped_result(script)
                script_results.append(skipped)
                monitor.on_script_started(job.job_id, script.definition.id, idx)
                monitor.on_script_completed(job.job_id, skipped)
                continue

            # 2. Dependency skip — unmet deps produce a FAILED result.
            unmet_deps = [dep for dep in script.depends_on if dep not in completed_tests]

            if unmet_deps:
                skipped_result = make_skipped_result(script, unmet_deps)
                script_results.append(skipped_result)
                monitor.on_script_started(job.job_id, script.definition.id, idx)
                monitor.on_script_completed(job.job_id, skipped_result)
                continue

            monitor.on_script_started(job.job_id, script.definition.id, idx)
            job.current_script = script.name

            script_result = await run_script(script, context, job.job_id, monitor, self._jobs)
            script_results.append(script_result)
            monitor.on_script_completed(job.job_id, script_result)

            if script_result.status == ScriptStatus.COMPLETED:
                completed_tests.add(script.name)
                self._propagate_script_outputs(script, context)

        return script_results



    @staticmethod
    def _propagate_script_outputs(script: TestScript, context: StepContext) -> None:
        """Promote script output variables to the shared namespace for downstream tests."""
        outputs = getattr(script.definition, "outputs", None) or {}
        for export_name, var_ref in outputs.items():
            value = context.get_variable(var_ref)
            if value is not None:
                context.set_variable(export_name, value)
                context.set_variable(f"!{script.name}:{export_name}", value)


def _target_release(tck: Tck) -> tuple[str, bool]:
    """Return the ecosystem release a TCK targets, and whether it said so itself.

    ADR-0019's ``dataspace`` block is the source of the version; the flat
    ``dataspace_version`` field is the older way of saying the same thing and
    is read when the block is absent. Whether it was stated at all matters:
    a release nobody declared is a default, and a default must never be held
    against an operator who bound a deployment of a different one.
    """
    definition = getattr(tck, "definition", None)
    if definition is None:
        return defaults.DATASPACE_VERSION, False

    dataspace = getattr(definition, "dataspace", None)
    if dataspace is not None and getattr(dataspace, "version", ""):
        return dataspace.version, True

    fields_set = getattr(definition, "model_fields_set", set())
    version = getattr(definition, "dataspace_version", "") or defaults.DATASPACE_VERSION
    return version, "dataspace_version" in fields_set


def _is_encrypted_tck(path: Path) -> bool:
    """Return True if the .tck ZIP contains payload.enc (encrypted package format)."""
    import zipfile
    try:
        with zipfile.ZipFile(path, "r") as zf:
            return "payload.enc" in zf.namelist()
    except Exception:
        return False

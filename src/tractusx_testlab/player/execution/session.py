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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A TCK run held open between tests, so a test can be run when it is asked for.

:meth:`TestlabPlayer.run_tck` opens a session, runs every test and closes it. A
host that lets a person drive the run (labs) keeps the session instead::

    session = await player.open_session(tck, runtime_vars, job_id)
    await session.run_scheduled()  # every test not marked ``async: true``
    await session.run_test("push.yaml")  # an ``async: true`` test, when asked, again
    result = await session.close()  # teardown, verdict, trace closed

Between calls nothing runs, but the bound infrastructure, the services, the mock
endpoints and the context stay up. Drive it from the loop that opened it: a
dynamic mock answers on that loop. Tests do not read each other's outputs (the
compiler refuses it), so one can run on its own; running it again replaces what
its previous attempt published, and its latest attempt is the one that counts.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tractusx_testlab.player.execution._trace_formatter import (
    build_tck_result,
    finalize_job,
    make_intentionally_skipped_result,
)
from tractusx_testlab.player.execution.phase import _PHASE_TO_NAMESPACE
from tractusx_testlab.player.execution.step_runner import run_test

if TYPE_CHECKING:
    from tractusx_testlab.authoring.test import Tck, Test
    from tractusx_testlab.logging.structured import StructuredLogger
    from tractusx_testlab.logging.trace import ExecutionTrace
    from tractusx_testlab.models import TckResult, TestResult
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.player.execution.monitor import ExecutionMonitor
    from tractusx_testlab.player.jobs import JobManager
    from tractusx_testlab.services.instances import ServiceManager


class SessionClosedError(RuntimeError):
    """The session was asked to run a test after it was closed."""


class TckSession:
    """One job's run of one TCK, kept open until :meth:`close`.

    Built by :meth:`TestlabPlayer.open_session`, which has already bound the
    infrastructure, seeded the context and started the services. One test runs
    at a time; a second request waits for the first.
    """

    __slots__ = (
        "_attempts",
        "_closed",
        "_context",
        "_job",
        "_job_logger",
        "_jobs",
        "_lock",
        "_monitor",
        "_on_close",
        "_records",
        "_result",
        "_results",
        "_services",
        "_skip_ids",
        "_started_at",
        "_tck",
        "_trace",
    )

    def __init__(
        self,
        *,
        tck: Tck,
        job: Any,
        context: StepContext,
        monitor: ExecutionMonitor,
        jobs: JobManager,
        services: ServiceManager,
        job_logger: StructuredLogger,
        trace: ExecutionTrace | None,
        skip_ids: frozenset[str],
        records: contextlib.ExitStack,
        on_close: Callable[[], None],
    ) -> None:
        self._tck = tck
        self._job = job
        self._context = context
        self._monitor = monitor
        self._jobs = jobs
        self._services = services
        self._job_logger = job_logger
        self._trace = trace
        self._skip_ids = skip_ids
        self._records = records
        self._on_close = on_close
        self._lock = asyncio.Lock()
        self._results: dict[str, TestResult] = {}
        self._attempts: dict[str, int] = {}
        self._started_at = datetime.now(UTC)
        self._closed = False
        self._result: TckResult | None = None

    # ------------------------------------------------------------------
    # What the session holds
    # ------------------------------------------------------------------

    @property
    def job_id(self) -> str:
        return self._job.job_id

    @property
    def tests(self) -> list[Test]:
        """Every test of the TCK, in manifest order."""
        return self._tck.tests

    @property
    def on_demand(self) -> list[Test]:
        """The tests the manifest marks ``async: true``, in manifest order."""
        return [test for test in self._tck.tests if test.on_demand]

    @property
    def closed(self) -> bool:
        return self._closed

    def attempts(self, test_id: str) -> int:
        """How many times the test *test_id* has run in this session."""
        return self._attempts.get(self._find(test_id)[1].test_id, 0)

    def latest(self, test_id: str) -> TestResult | None:
        """The result of the latest attempt of *test_id*, or ``None`` before the first."""
        return self._results.get(self._find(test_id)[1].test_id)

    # ------------------------------------------------------------------
    # Running tests
    # ------------------------------------------------------------------

    async def run_all(self) -> list[TestResult]:
        """Run every test in manifest order, ``async: true`` ones included (a plain run)."""
        return [
            result
            for idx, test in enumerate(self._tck.tests)
            if (result := await self._run_scheduled(idx, test)) is not None
        ]

    async def run_scheduled(self) -> list[TestResult]:
        """Run every test that is not ``async: true``, then announce those that are.

        ``test.awaiting`` follows the rest, so a viewer offers them once nothing runs.
        """
        results = [
            result
            for idx, test in enumerate(self._tck.tests)
            if not test.on_demand and (result := await self._run_scheduled(idx, test)) is not None
        ]
        for idx, test in enumerate(self._tck.tests):
            if test.on_demand and test.test_id not in self._results:
                self._monitor.on_test_awaiting(self.job_id, test.definition.id, idx)
        return results

    async def run_test(self, test_id: str) -> TestResult:
        """Run the test *test_id* now, again if it ran before.

        *test_id* is the manifest entry (``push.yaml``) or the test's own ``id``.
        ``skip_tests`` decides what runs on its own, not what a person asks for.

        Raises:
            KeyError: No test of this TCK has that id.
            SessionClosedError: The session was closed.
        """
        idx, test = self._find(test_id)
        async with self._lock:
            self._require_open()
            return await self._run(idx, test)

    async def close(self) -> TckResult:
        """Tear the session down and deliver the verdict (latest attempts); idempotent.

        A test that never ran (skipped, or ``async: true`` and never asked for) is
        skipped. The services, the mock server and the transcript are released even
        when publishing that raises (a host abandoning a cancelled run does).
        """
        async with self._lock:
            if self._closed:
                if self._result is None:
                    raise SessionClosedError(f"The session of job '{self.job_id}' failed to close")
                return self._result
            self._closed = True
            try:
                try:
                    for idx, test in enumerate(self._tck.tests):
                        if test.test_id not in self._results:
                            self._skip(idx, test)
                finally:
                    self._services.teardown()
                    self._on_close()
                results = [self._results[test.test_id] for test in self._tck.tests]
                result = build_tck_result(
                    self._tck.name, results, self._started_at, datetime.now(UTC)
                )
                finalize_job(
                    self._jobs, self._job, result, self._monitor, self._job_logger, self._trace
                )
                self._result = result
            finally:
                self._records.close()
            return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _run_scheduled(self, idx: int, test: Test) -> TestResult | None:
        """Run *test* as part of the planned sequence, honouring the operator's skips."""
        async with self._lock:
            self._require_open()
            if test.test_id in self._skip_ids:
                self._skip(idx, test)
                return self._results[test.test_id]
            return await self._run(idx, test)

    async def _run(self, idx: int, test: Test) -> TestResult:
        attempt = self._attempts.get(test.test_id, 0) + 1
        if attempt > 1:
            self._forget_outputs(test)
        self._attempts[test.test_id] = attempt
        self._monitor.on_test_started(self.job_id, test.definition.id, idx, attempt)
        self._job.current_test = test.name
        result = await run_test(test, self._context, self.job_id, self._monitor, self._jobs)
        self._results[test.test_id] = result
        self._monitor.on_test_completed(self.job_id, result)
        return result

    def _skip(self, idx: int, test: Test) -> None:
        skipped = make_intentionally_skipped_result(test)
        self._results[test.test_id] = skipped
        self._monitor.on_test_started(self.job_id, test.definition.id, idx)
        self._monitor.on_test_completed(self.job_id, skipped)

    def _forget_outputs(self, test: Test) -> None:
        """Drop what *test*'s previous attempt published under ``<phase>.<step id>.``.

        Else a step failing before it publishes leaves the old value for later steps.
        """
        prefixes = tuple(
            f"{_PHASE_TO_NAMESPACE[phase]}.{step.id}."
            for phase, steps in (
                ("setup", test.setup),
                ("execution", test.steps),
                ("teardown", test.teardown),
            )
            for step in steps
            if getattr(step, "id", None)
        )
        if not prefixes:
            return
        for name in self._context.variables:
            if name.startswith(prefixes):
                self._context.unset_variable(name)

    def _find(self, test_id: str) -> tuple[int, Test]:
        for idx, test in enumerate(self._tck.tests):
            if test_id in (test.test_id, test.definition.id):
                return idx, test
        raise KeyError(f"TCK '{self._tck.id}' has no test '{test_id}'")

    def _require_open(self) -> None:
        if self._closed:
            raise SessionClosedError(f"The session of job '{self.job_id}' is closed")

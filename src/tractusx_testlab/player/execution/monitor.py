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

"""ExecutionMonitor — the engine's single event publisher.

Every part of the engine reports its transitions through the typed ``on_*``
methods below rather than hand-building an event dict at the call site: each
wraps its arguments in the matching model from ``models.runtime.events`` and
publishes it under its wire name (``step_completed`` -> ``step.completed``).

One transition, two records, because they have two audiences: the **log** — the
console transcript, for a person watching — and the **trace** — CloudEvents
JSONL per ADR-0016, for the IDE, the report and anyone debugging the wire.
Assertions are the one place the two differ in shape: the log prints a line per
check as it is evaluated, the trace nests them in the step's terminal event,
because ADR-0016 requires a step result to be self-contained for its renderer.

The trace is written first so the id it returns can go on the log line: a line
about a call names the event that holds that call's headers and body.

See ``docs/developer/execution-events.md`` for the full event contract.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable
from typing import Any

from tractusx_testlab.logging import wire
from tractusx_testlab.logging.masking import mask
from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models.primitives.enums import EventKind
from tractusx_testlab.models.runtime.events import (
    ExecutionEvent,
    JobCancelledEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobHeldEvent,
    JobPausedEvent,
    JobRestoredEvent,
    JobResumedEvent,
    JobStartedEvent,
    TestAwaitingEvent,
    TestCompletedEvent,
    TestStartedEvent,
)
from tractusx_testlab.models.runtime.results import TestResult
from tractusx_testlab.player.checkpoints import CheckpointTracker
from tractusx_testlab.player.execution._monitor_inbound import InboundEvents
from tractusx_testlab.player.execution._monitor_selection import SelectionEvents
from tractusx_testlab.player.execution._monitor_steps import StepEvents
from tractusx_testlab.player.execution._trace_publisher import TracePublisher

# Callback signature: (wire_event_name, payload_dict) -> None
CallbackFn = Callable[[str, dict[str, Any]], Any]
# Trace callback signature: (wire_event_name, payload_dict, cloud_event | None) -> None
TraceCallbackFn = Callable[[str, dict[str, Any], dict[str, Any] | None], Any]


class ExecutionMonitor(StepEvents, InboundEvents, SelectionEvents):
    """Publishes typed execution events, logs them, traces them, fires callbacks.

    The step lifecycle — the events published while a step runs — is
    :class:`StepEvents`, :class:`InboundEvents` and :class:`SelectionEvents`,
    each in its own module, and the run's checkpoints are followed by their
    common base (``_monitor_checkpoints``); the job and test lifecycle, the
    package verification and the publishing itself are here.
    """

    __slots__ = (
        "_background_tasks",
        "_callbacks",
        "_checkpoints",
        "_logger",
        "_occurrences",
        "_trace",
        "_trace_callbacks",
    )

    def __init__(self, logger: StructuredLogger, trace: ExecutionTrace | None = None) -> None:
        """Initialize with a console logger and, optionally, an execution trace.

        The trace is optional so an embedder that only wants the transcript pays
        for nothing else; a monitor without one still logs and still fires
        callbacks, and the ``_trace_*`` helpers below are the only code that has
        to notice its absence.
        """
        self._logger = logger
        self._trace = TracePublisher(trace)
        self._callbacks: list[CallbackFn] = []
        self._trace_callbacks: list[TraceCallbackFn] = []
        self._background_tasks: set[asyncio.Task] = set()
        self._checkpoints: CheckpointTracker | None = None
        self._occurrences: Counter[tuple[str, ...]] = Counter()

    @property
    def trace(self) -> ExecutionTrace | None:
        """The CloudEvents trace this monitor writes, if it writes one."""
        return self._trace.trace

    def follow_checkpoints(self, tracker: CheckpointTracker) -> None:
        """Tell *tracker* what the run does from now on — the player binds the run's own."""
        self._checkpoints = tracker

    def add_callback(self, fn: CallbackFn) -> None:
        """Register a callback function to be invoked on every event."""
        self._callbacks.append(fn)

    def remove_callback(self, fn: CallbackFn) -> None:
        """Stop invoking *fn*; one never registered is ignored."""
        if fn in self._callbacks:
            self._callbacks.remove(fn)

    def add_trace_callback(self, fn: TraceCallbackFn) -> None:
        """Register *fn* for every event, with the CloudEvent the trace wrote for it.

        *fn* is called as ``fn(event, payload, envelope)``: the same two as an
        :meth:`add_callback` callback, and the ADR-0016 envelope — ``id``,
        ``type``, ``source``, ``time``, ``sequence`` and ``data`` exactly as the
        JSONL line has them — or ``None`` for an event the trace does not write
        on its own (``assertion_result``, nested in its step's terminal event;
        the package verification). A host that stores the envelope's ``id``
        names the event as the player's trace does (ADR-0016, ADR-0028).
        """
        self._trace_callbacks.append(fn)

    def forward_to(self, other: ExecutionMonitor) -> None:
        """Hand every event this monitor publishes to *other*'s callbacks too, as they are then."""
        self.add_trace_callback(other._dispatch)

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def on_job_started(self, job_id: str, tck_id: str) -> None:
        event_id = self._trace.run_started(job_id, tck_id)
        self._publish(JobStartedEvent(job_id=job_id, tck_id=tck_id), event_id)

    def on_job_paused(self, job_id: str) -> None:
        occurrence = self._occurrence("job_paused", job_id)
        self._publish(JobPausedEvent(job_id=job_id, occurrence=occurrence))

    def on_job_resumed(self, job_id: str) -> None:
        occurrence = self._occurrence("job_resumed", job_id)
        self._publish(JobResumedEvent(job_id=job_id, occurrence=occurrence))

    def on_job_held(self, job_id: str, withdrawn: list[str], kept: dict[str, str]) -> None:
        """The paused run has stopped and withdrawn its offers (``player.execution.hold``)."""
        occurrence = self._occurrence("job_held", job_id)
        event_id = self._trace.run_held(withdrawn, kept, occurrence)
        event = JobHeldEvent(job_id=job_id, withdrawn=withdrawn, kept=kept, occurrence=occurrence)
        self._publish(event, event_id)

    def on_job_restored(self, job_id: str, restored: list[str], lost: dict[str, str]) -> None:
        """The held run has put its offers back and goes on."""
        occurrence = self._occurrence("job_restored", job_id)
        event_id = self._trace.run_restored(restored, lost, occurrence)
        event = JobRestoredEvent(job_id=job_id, restored=restored, lost=lost, occurrence=occurrence)
        self._publish(event, event_id)

    def on_job_completed(self, job_id: str) -> None:
        event_id = self._trace.run_ended(job_id, "PASSED")
        self._publish(JobCompletedEvent(job_id=job_id), event_id)
        self._follow("job_ended", self._cause("job_completed"))

    def on_job_failed(self, job_id: str, error: str | None = None) -> None:
        event_id = self._trace.run_ended(job_id, "FAILED", error)
        self._publish(JobFailedEvent(job_id=job_id, error=error), event_id)
        self._follow("job_ended", self._cause("job_failed"))

    def on_job_cancelled(self, job_id: str) -> None:
        event_id = self._trace.run_ended(job_id, "CANCELLED")
        self._publish(JobCancelledEvent(job_id=job_id), event_id)
        self._follow("job_ended", self._cause("job_cancelled"))

    # ------------------------------------------------------------------
    # Test lifecycle
    # ------------------------------------------------------------------

    def on_test_started(self, job_id: str, test: str, index: int, attempt: int = 1) -> None:
        event_id = self._trace.test_started(test, index, attempt)
        self._publish(
            TestStartedEvent(job_id=job_id, test_id=test, index=index, attempt=attempt), event_id
        )
        self._follow("test_started", test, self._cause("test_started"))

    def on_test_awaiting(self, job_id: str, test: str, index: int) -> None:
        """An on-demand test is ready and waits for someone to run it."""
        occurrence = self._occurrence("test_awaiting", job_id, test)
        event_id = self._trace.test_awaiting(test, index, occurrence)
        event = TestAwaitingEvent(job_id=job_id, test_id=test, index=index, occurrence=occurrence)
        self._publish(event, event_id)

    def on_test_completed(self, job_id: str, result: TestResult, attempt: int = 1) -> None:
        """Publish a test_completed event; ``result.status`` carries the outcome."""
        # The event repeats every step, so it repeats them as they were written
        # down: the real calls, masked.
        record = result.model_copy(
            update={"execution": [wire.as_recorded(step) for step in result.execution]}
        )
        event_id = self._trace.test_ended(result, attempt)
        self._publish(TestCompletedEvent(job_id=job_id, result=record, attempt=attempt), event_id)
        test_id = result.test_id or result.test_name
        self._follow("test_ended", test_id, result.status, self._cause("test_completed"))

    # ------------------------------------------------------------------
    # Package verification (pre-execution — no job exists yet)
    # ------------------------------------------------------------------

    def on_package_verify_start(self, package: str, encrypted: bool) -> None:
        self._emit("tck.package.verify.start", package=package, encrypted=encrypted)

    def on_package_verify_passed(self, package: str, checksum: str) -> None:
        """Emit event when fingerprint and checksum verification succeeds."""
        self._emit("tck.package.verify.passed", package=package, checksum=checksum)

    def on_package_verify_failed(self, package: str, error: str) -> None:
        self._emit("tck.package.verify.failed", package=package, error=error)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, event: ExecutionEvent, event_id: str | None = None) -> None:
        """Dump a typed event and dispatch it under its canonical wire name.

        *event_id* — the CloudEvent this was traced as — goes to the transcript,
        and its envelope to the trace callbacks. An assertion is given its
        step's id for the transcript, but not its step's envelope.
        """
        wire_event = event.kind.value.replace("_", ".", 1)
        nested = event.kind is EventKind.ASSERTION_RESULT
        envelope = None if nested else self._trace.envelope(event_id)
        self._emit(
            wire_event, event_id=event_id, _envelope=envelope, **event.model_dump(mode="json")
        )

    def _emit(
        self,
        event: str,
        *,
        event_id: str | None = None,
        _envelope: dict[str, Any] | None = None,
        **payload: Any,
    ) -> None:
        # What an embedder receives is what a viewer of it will see, so a secret
        # the run minted is masked before either audience gets the event.
        payload = mask(payload)
        self._logger.info(event, event_id=event_id, **payload)
        self._dispatch(event, payload, _envelope)

    def _dispatch(
        self, event: str, payload: dict[str, Any], envelope: dict[str, Any] | None
    ) -> None:
        """Hand an event to every callback: the plain ones, then the trace ones with *envelope*."""
        targets: list[tuple[Callable[..., Any], tuple[Any, ...]]] = [
            *((fn, (event, payload)) for fn in self._callbacks),
            *((fn, (event, payload, envelope)) for fn in self._trace_callbacks),
        ]
        for callback, args in targets:
            try:
                result = callback(*args)
                if asyncio.iscoroutine(result):
                    task = asyncio.ensure_future(result)
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except (RuntimeError, TypeError, ValueError) as exc:
                self._logger.warning(f"Callback failed for event '{event}': {exc}")

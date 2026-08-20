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
from collections.abc import Callable
from typing import Any

from tractusx_testlab.logging import wire
from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.events import (
    AssertionResultEvent,
    ExecutionEvent,
    JobCancelledEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobPausedEvent,
    JobResumedEvent,
    JobStartedEvent,
    ScriptCompletedEvent,
    ScriptStartedEvent,
    StepCallEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepSkippedEvent,
    StepStartedEvent,
    StepWaitingEvent,
)
from tractusx_testlab.models.runtime.results import HttpExchange, ScriptResult, StepResult
from tractusx_testlab.player.execution._trace_publisher import TracePublisher

# Callback signature: (wire_event_name, payload_dict) -> None
CallbackFn = Callable[[str, dict[str, Any]], Any]


class ExecutionMonitor:
    """Publishes typed execution events, logs them, traces them, fires callbacks."""

    __slots__ = ("_background_tasks", "_callbacks", "_logger", "_trace")

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
        self._background_tasks: set[asyncio.Task] = set()

    @property
    def trace(self) -> ExecutionTrace | None:
        """The CloudEvents trace this monitor writes, if it writes one."""
        return self._trace.trace

    def add_callback(self, fn: CallbackFn) -> None:
        """Register a callback function to be invoked on every event."""
        self._callbacks.append(fn)

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def on_job_started(self, job_id: str, tck_id: str) -> None:
        event_id = self._trace.run_started(job_id, tck_id)
        self._publish(JobStartedEvent(job_id=job_id, tck_id=tck_id), event_id)

    def on_job_paused(self, job_id: str) -> None:
        self._publish(JobPausedEvent(job_id=job_id))

    def on_job_resumed(self, job_id: str) -> None:
        self._publish(JobResumedEvent(job_id=job_id))

    def on_job_completed(self, job_id: str) -> None:
        event_id = self._trace.run_ended(job_id, "PASSED")
        self._publish(JobCompletedEvent(job_id=job_id), event_id)

    def on_job_failed(self, job_id: str, error: str | None = None) -> None:
        event_id = self._trace.run_ended(job_id, "FAILED", error)
        self._publish(JobFailedEvent(job_id=job_id, error=error), event_id)

    def on_job_cancelled(self, job_id: str) -> None:
        event_id = self._trace.run_ended(job_id, "CANCELLED")
        self._publish(JobCancelledEvent(job_id=job_id), event_id)

    # ------------------------------------------------------------------
    # Script lifecycle
    # ------------------------------------------------------------------

    def on_script_started(self, job_id: str, script: str, index: int) -> None:
        event_id = self._trace.test_started(script, index)
        self._publish(ScriptStartedEvent(job_id=job_id, script=script, index=index), event_id)

    def on_script_completed(self, job_id: str, result: ScriptResult) -> None:
        """Publish a script_completed event; ``result.status`` carries the outcome."""
        # The event repeats every step, so it repeats them as they were written
        # down: the real calls, masked.
        record = result.model_copy(
            update={"execution": [wire.as_recorded(step) for step in result.execution]}
        )
        event_id = self._trace.test_ended(result)
        self._publish(ScriptCompletedEvent(job_id=job_id, result=record), event_id)

    # ------------------------------------------------------------------
    # Step lifecycle
    # ------------------------------------------------------------------

    def on_step_started(
        self,
        job_id: str,
        script: str,
        step_id: str | None,
        step_index: int,
        step_type: str,
        step_name: str,
        phase: str = "main",
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Publish a step_started event.

        *inputs* is the step's ``with:`` block with its references resolved —
        the values the step is about to be given, not the template naming them.
        """
        event_id = self._trace.step_started(script, step_id, step_index, step_type, phase, inputs)
        self._publish(
            StepStartedEvent(
                job_id=job_id,
                script=script,
                step_id=step_id,
                step_index=step_index,
                step_type=step_type,
                step_name=step_name,
                phase=phase,
                inputs=inputs,
            ),
            event_id,
        )

    def on_step_call(
        self,
        job_id: str,
        script: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        index: int,
        call: HttpExchange,
    ) -> None:
        """Publish one call a step made, as soon as its answer came back.

        While the step is still running, which is the point: a DSP pull polls a
        negotiation for a minute, and the polls are what somebody watching needs
        to see (:class:`~tractusx_testlab.models.runtime.events.StepCallEvent`).
        """
        event_id = self._trace.step_call(script, step_id, step_type, phase, index, call)
        self._publish(
            StepCallEvent(
                job_id=job_id,
                script=script,
                step_id=step_id,
                step_type=step_type,
                index=index,
                call=call,
            ),
            event_id,
        )

    def on_step_completed(
        self,
        job_id: str,
        script: str,
        step_id: str | None,
        result: StepResult,
    ) -> None:
        """Publish one assertion_result event per assertion, then the step outcome.

        The outcome kind (step_completed / step_failed / step_skipped) is
        derived from ``result.status`` — the one place that status lives —
        so a consumer never has to sniff ``step_type`` to know what happened.
        """
        # What is written down is not what the run keeps: the record carries the
        # call the SDK really made, masked, while the result keeps the exchange
        # the step named — which is what a ``returns:`` block reads (logging.wire).
        record = wire.as_recorded(result)

        # The assertion lines are given the step's id on purpose: they have no
        # event of their own — ADR-0016 nests them in the terminal event, which
        # is where a reader following the id finds them.
        event_id = self._trace.step_ended(script, step_id, record)

        for index, assertion_result in enumerate(result.assertions):
            self._publish(
                AssertionResultEvent(
                    job_id=job_id,
                    script=script,
                    step_id=step_id,
                    step_name=result.step_name,
                    index=index,
                    assertion=assertion_result,
                ),
                event_id,
            )

        outcome = {StepStatus.FAILED: StepFailedEvent, StepStatus.SKIPPED: StepSkippedEvent}.get(
            result.status, StepCompletedEvent
        )
        self._publish(
            outcome(job_id=job_id, script=script, step_id=step_id, result=record), event_id
        )

    def on_step_waiting(self, job_id: str, step_index: int, listener_url: str) -> None:
        event_id = self._trace.step_waiting(step_index, listener_url)
        self._publish(
            StepWaitingEvent(job_id=job_id, step_index=step_index, listener_url=listener_url),
            event_id,
        )

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

        *event_id* — the CloudEvent this was traced as — goes to the transcript
        only: a consumer receives the typed event verbatim, as promised.
        """
        wire_event = event.kind.value.replace("_", ".", 1)
        self._emit(wire_event, event_id=event_id, **event.model_dump(mode="json"))

    def _emit(self, event: str, *, event_id: str | None = None, **payload: Any) -> None:
        self._logger.info(event, event_id=event_id, **payload)
        for callback in self._callbacks:
            try:
                result = callback(event, payload)
                if asyncio.iscoroutine(result):
                    task = asyncio.ensure_future(result)
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except (RuntimeError, TypeError, ValueError) as exc:
                self._logger.warning(f"Callback failed for event '{event}': {exc}")

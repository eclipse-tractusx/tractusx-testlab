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

"""ExecutionMonitor — the engine's single event publisher.

Every part of the execution engine (the player, the phase runners, the step
runner) reports job/script/step lifecycle transitions through the typed
``on_*`` methods below instead of hand-building an event dict at the call
site. Each method wraps its arguments in the matching pydantic model from
``models.runtime.events`` — every one of which carries an explicit ``kind``
discriminator — and publishes it under its canonical SSE wire name (the
``kind`` value with its single underscore turned into a dot, e.g.
``step_completed`` -> ``step.completed``).

See ``docs/developer/execution-events.md`` for the full event contract.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tractusx_testlab.logging.structured import StructuredLogger
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
    StepCompletedEvent,
    StepFailedEvent,
    StepSkippedEvent,
    StepStartedEvent,
    StepWaitingEvent,
)
from tractusx_testlab.models.runtime.results import ScriptResult, StepResult

# Callback signature: (wire_event_name, payload_dict) -> None
CallbackFn = Callable[[str, dict[str, Any]], Any]


class ExecutionMonitor:
    """Publishes typed execution events, logs them, and fires callbacks."""

    __slots__ = ("_background_tasks", "_callbacks", "_logger")

    def __init__(self, logger: StructuredLogger) -> None:
        """Initialize with a structured logger for event recording."""
        self._logger = logger
        self._callbacks: list[CallbackFn] = []
        self._background_tasks: set[asyncio.Task] = set()

    def add_callback(self, fn: CallbackFn) -> None:
        """Register a callback function to be invoked on every event."""
        self._callbacks.append(fn)

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def on_job_started(self, job_id: str, tck_id: str) -> None:
        """Publish a job_started event."""
        self._publish(JobStartedEvent(job_id=job_id, tck_id=tck_id))

    def on_job_paused(self, job_id: str) -> None:
        """Publish a job_paused event."""
        self._publish(JobPausedEvent(job_id=job_id))

    def on_job_resumed(self, job_id: str) -> None:
        """Publish a job_resumed event."""
        self._publish(JobResumedEvent(job_id=job_id))

    def on_job_completed(self, job_id: str) -> None:
        """Publish a job_completed event."""
        self._publish(JobCompletedEvent(job_id=job_id))

    def on_job_failed(self, job_id: str, error: str | None = None) -> None:
        """Publish a job_failed event."""
        self._publish(JobFailedEvent(job_id=job_id, error=error))

    def on_job_cancelled(self, job_id: str) -> None:
        """Publish a job_cancelled event."""
        self._publish(JobCancelledEvent(job_id=job_id))

    # ------------------------------------------------------------------
    # Script lifecycle
    # ------------------------------------------------------------------

    def on_script_started(self, job_id: str, script: str, index: int) -> None:
        """Publish a script_started event."""
        self._publish(ScriptStartedEvent(job_id=job_id, script=script, index=index))

    def on_script_completed(self, job_id: str, result: ScriptResult) -> None:
        """Publish a script_completed event; ``result.status`` carries the outcome."""
        self._publish(ScriptCompletedEvent(job_id=job_id, result=result))

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
    ) -> None:
        """Publish a step_started event."""
        self._publish(StepStartedEvent(
            job_id=job_id,
            script=script,
            step_id=step_id,
            step_index=step_index,
            step_type=step_type,
            step_name=step_name,
            phase=phase,
        ))

    def on_step_completed(
        self, job_id: str, script: str, step_id: str | None, result: StepResult,
    ) -> None:
        """Publish one assertion_result event per assertion, then the step outcome.

        The outcome kind (step_completed / step_failed / step_skipped) is
        derived from ``result.status`` — the one place that status lives —
        so a consumer never has to sniff ``step_type`` to know what happened.
        """
        for index, assertion_result in enumerate(result.assertions):
            self._publish(AssertionResultEvent(
                job_id=job_id,
                script=script,
                step_id=step_id,
                step_name=result.step_name,
                index=index,
                assertion=assertion_result,
            ))

        if result.status == StepStatus.FAILED:
            self._publish(StepFailedEvent(job_id=job_id, script=script, step_id=step_id, result=result))
        elif result.status == StepStatus.SKIPPED:
            self._publish(StepSkippedEvent(job_id=job_id, script=script, step_id=step_id, result=result))
        else:
            self._publish(StepCompletedEvent(job_id=job_id, script=script, step_id=step_id, result=result))

    def on_step_waiting(self, job_id: str, step_index: int, listener_url: str) -> None:
        """Publish a step_waiting event."""
        self._publish(StepWaitingEvent(job_id=job_id, step_index=step_index, listener_url=listener_url))

    # ------------------------------------------------------------------
    # Package verification (pre-execution — no job exists yet)
    # ------------------------------------------------------------------

    def on_package_verify_start(self, package: str, encrypted: bool) -> None:
        """Emit event when package integrity verification begins."""
        self._emit("tck.package.verify.start", package=package, encrypted=encrypted)

    def on_package_verify_passed(self, package: str, checksum: str) -> None:
        """Emit event when fingerprint and checksum verification succeeds."""
        self._emit("tck.package.verify.passed", package=package, checksum=checksum)

    def on_package_verify_failed(self, package: str, error: str) -> None:
        """Emit event when package integrity verification fails."""
        self._emit("tck.package.verify.failed", package=package, error=error)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, event: ExecutionEvent) -> None:
        """Dump a typed event and dispatch it under its canonical wire name."""
        wire_event = event.kind.value.replace("_", ".", 1)
        self._emit(wire_event, **event.model_dump(mode="json"))

    def _emit(self, event: str, **payload: Any) -> None:
        self._logger.info(event, **payload)
        for callback in self._callbacks:
            try:
                result = callback(event, payload)
                if asyncio.iscoroutine(result):
                    task = asyncio.ensure_future(result)
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
            except (RuntimeError, TypeError, ValueError) as exc:
                self._logger.warning(f"Callback failed for event '{event}': {exc}")

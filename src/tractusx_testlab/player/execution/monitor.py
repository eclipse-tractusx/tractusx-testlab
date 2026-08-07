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

"""ExecutionMonitor — tracks step/script progress and emits callbacks."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.models import (
    JobStatus,
    ScriptResult,
    StepResult,
)


# Callback signature: (event_name, payload_dict) -> None
CallbackFn = Callable[[str, dict[str, Any]], Any]


class ExecutionMonitor:
    """Observes execution progress, logs structured events, and fires callbacks."""

    __slots__ = ("_logger", "_callbacks", "_background_tasks")

    def __init__(self, logger: StructuredLogger) -> None:
        """Initialize with a structured logger for event recording."""
        self._logger = logger
        self._callbacks: list[CallbackFn] = []
        self._background_tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]

    def add_callback(self, fn: CallbackFn) -> None:
        """Register a callback function to be invoked on every event."""
        self._callbacks.append(fn)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def on_job_started(self, event: str, job_id: str, tck: str) -> None:
        """Emit event when a job execution begins."""
        self._emit(event, job_id=job_id, tck=tck)

    def on_script_started(self, event: str, job_id: str, script_name: str, index: int) -> None:
        """Emit event when a script within a job starts executing."""
        self._emit(event, job_id=job_id, script=script_name, index=index)

    def on_step_started(self, event: str, job_id: str, step_index: int, step_type: str, step_name: str = "", phase: str = "main") -> None:
        """Emit event when an individual step begins execution."""
        self._emit(
            event,
            job_id=job_id,
            step_index=step_index,
            step_name=step_name,
            step_type=step_type,
            phase=phase,
            status="running",
        )

    def on_step_completed(self, event: str, job_id: str, result: StepResult) -> None:
        """Emit event when a step finishes with its result details."""
        payload: dict[str, Any] = {
            "job_id": job_id,
            "step_name": result.step_name,
            "step_type": result.step_type,
            "phase": result.phase.value.lower(),
            "status": result.status.value,
            "duration_s": result.duration_s,
        }
        if result.request:
            payload["request"] = result.request.model_dump(exclude_none=True)
        if result.response:
            payload["response"] = result.response.model_dump(exclude_none=True)
        if result.error:
            payload["error"] = result.error
        self._emit(event, **payload)

    def on_step_waiting(self, event: str, job_id: str, step_index: int, listener_url: str) -> None:
        """Emit event when a step is waiting for an async callback."""
        self._emit(event, job_id=job_id, step_index=step_index, listener_url=listener_url)

    def on_script_completed(self, event: str, job_id: str, result: ScriptResult) -> None:
        """Emit event when a script finishes execution."""
        self._emit(
            event,
            job_id=job_id,
            script=result.script_name,
            status=result.status.value,
        )

    def on_job_completed(self, event: str, job_id: str, status: JobStatus) -> None:
        """Emit event when a job finishes with final status."""
        self._emit(event, job_id=job_id, status=status.value)

    def on_job_paused(self, event: str, job_id: str) -> None:
        """Emit event when a job is paused."""
        self._emit(event, job_id=job_id)

    def on_job_resumed(self, event: str, job_id: str) -> None:
        """Emit event when a paused job resumes."""
        self._emit(event, job_id=job_id)

    def log_event(self, event_name: str, **payload: Any) -> None:
        """Single external entry point — routes to the matching on_* method."""
        event = self._get_tck_event(event_name, **payload)
        if event_name == "job.started":
            self.on_job_started(event, payload["job_id"], payload["tck_id"])
        elif event_name == "script.started":
            self.on_script_started(event, payload["job_id"], payload["script"], payload["index"])
        elif event_name == "step.started":
            self.on_step_started(
                event,
                payload["job_id"],
                payload["step_index"],
                payload["step_type"],
                payload.get("step_name", ""),
                payload.get("phase", "main"),
            )
        elif event_name == "step.completed":
            self.on_step_completed(event, payload["job_id"], payload["result"])
        elif event_name == "step.waiting":
            self.on_step_waiting(event, payload["job_id"], payload["step_index"], payload["listener_url"])
        elif event_name == "script.completed":
            self.on_script_completed(event, payload["job_id"], payload["result"])
        elif event_name == "job.completed":
            self.on_job_completed(event, payload["job_id"], payload["status"])
        elif event_name == "job.paused":
            self.on_job_paused(event, payload["job_id"])
        elif event_name == "job.resumed":
            self.on_job_resumed(event, payload["job_id"])

    def _get_tck_event(self, event_name: str, **payload: Any) -> str:
        # tck_id may arrive as tck_id (steps) or tck (job.started alias).
        tck_id = payload.get("tck_id") or payload.get("tck")
        if not tck_id:
            return "[" + event_name + "]"
        parts: list[str] = [f"[{tck_id}"]
        # script → test segment; step_id → step segment (raw id, not formatted name).
        if payload.get("script") is not None:
            parts.append(str(payload["script"]))
        if payload.get("step_id") is not None:
            parts.append(str(payload["step_id"]))
        parts.append(event_name + "]")
        return "/".join(parts)

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

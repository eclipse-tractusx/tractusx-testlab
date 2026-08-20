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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.


"""Publishing a run's CloudEvents, or publishing nothing.

Held by the monitor instead of an ``ExecutionTrace | None`` and a guard at every
call site: a publisher with no trace is a working publisher that writes nowhere,
so "this engine is not tracing" is expressed once, here, rather than nine times
in the monitor. The vocabulary it publishes in is
:mod:`~tractusx_testlab.player.execution._trace_events`.

Every method hands back the ``id`` of the event it wrote — the path naming where
in the run the event happened — or ``None`` when this engine is not tracing. The
monitor prints it on the matching transcript line, which is what lets a reader
take a line off the console and find the whole event, headers and bodies
included, in the trace.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.logging.trace import SOURCE_LIFECYCLE, ExecutionTrace
from tractusx_testlab.models.runtime.results import ScriptResult, StepResult
from tractusx_testlab.player.execution._trace_events import (
    call_data,
    step_data,
    step_event_type,
    test_data,
    test_event_type,
)


class TracePublisher:
    """Publishes a run's CloudEvents, or publishes nothing.

    The monitor holds one of these instead of an ``ExecutionTrace | None`` and a
    guard at every call site: a publisher with no trace is a working publisher
    that writes nowhere, so "this engine is not tracing" is expressed once, here,
    rather than nine times in the monitor.
    """

    __slots__ = ("_trace",)

    def __init__(self, trace: ExecutionTrace | None = None) -> None:
        self._trace = trace

    @property
    def trace(self) -> ExecutionTrace | None:
        return self._trace

    def emit(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        source: str = SOURCE_LIFECYCLE,
        scope: tuple[str, ...] = (),
    ) -> str | None:
        """Write one event and return its id, or ``None`` when not tracing."""
        if self._trace is None:
            return None
        # A step names itself by its ``uses``; a lifecycle event has no step to name.
        envelope = self._trace.emit(
            event_type, data, source=source or SOURCE_LIFECYCLE, scope=scope
        )
        return str(envelope["id"])

    def run_started(self, job_id: str, tck_id: str) -> str | None:
        return self.emit("tck.start", {"tck_id": tck_id, "run_id": job_id})

    def run_ended(self, job_id: str, status: str, error: str | None = None) -> str | None:
        data: dict[str, Any] = {"status": status, "run_id": job_id}
        if error:
            data["errors"] = [{"code": "RUN_FAILED", "message": error, "retryable": False}]
        return self.emit("tck.end", data)

    def test_started(self, script: str, index: int) -> str | None:
        return self.emit("tck.test.start", {"test_id": script, "index": index}, scope=(script,))

    def test_ended(self, result: ScriptResult) -> str | None:
        test_id = result.script_id or result.script_name
        return self.emit(test_event_type(result.status), test_data(result), scope=(test_id,))

    def step_started(
        self,
        script: str,
        step_id: str | None,
        step_index: int,
        step_type: str,
        phase: str,
        inputs: dict[str, Any] | None = None,
    ) -> str | None:
        """The step is about to run, and this is what it is about to be given.

        ``inputs`` is the ``with:`` block with every ``${{ … }}`` reference
        substituted for the value the run seeded or produced. A trace that
        repeated the template instead named the variable and never said what it
        held, which is the one thing the reader opened the trace for. A
        reference that names nothing in scope leaves the block as written; the
        terminal event reports that as the step's failure.
        """
        data: dict[str, Any] = {"attempt": 1, "index": step_index, "phase": phase}
        if inputs:
            data["inputs"] = inputs
        return self.emit(
            "tck.test.step.start",
            data,
            source=step_type,
            scope=(script, phase, step_id or str(step_index)),
        )

    def step_call(
        self,
        script: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        index: int,
        call: Any,
    ) -> str | None:
        """One call the step made, published while the step is still running.

        Its path is the step's path plus which call it was, so dropping a phase
        from a trace with a prefix match drops its calls with it — and a step the
        script did not name falls back to what it *is*, which is the only thing
        left to name it by.
        """
        return self.emit(
            "tck.test.step.call",
            call_data(index, call),
            source=step_type,
            scope=(script, phase, step_id or step_type.rsplit("/", 1)[-1], "calls", str(index)),
        )

    def step_ended(self, script: str, step_id: str | None, result: StepResult) -> str | None:
        """One terminal event carrying the checks, the wire, and the error.

        No separate assertion events: ADR-0016 nests them in ``validations``.
        """
        return self.emit(
            step_event_type(result.status),
            step_data(result),
            source=result.step_type,
            scope=(script, result.phase.value.lower(), step_id or result.step_name),
        )

    def step_waiting(self, step_index: int, listener_url: str) -> str | None:
        return self.emit(
            "tck.test.step.update",
            {"attempt": 1, "state": "waiting", "listener_url": listener_url},
            scope=(str(step_index),),
        )

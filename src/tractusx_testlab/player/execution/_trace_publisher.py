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

A step's events carry its *marks* (``StepEvents.marks``): which run of the step
this is (``attempt``), the checkpoint it is (``checkpoint``) and, for a question
asked again after a pause, how many pauses it has been through (``pauses``) —
what keeps two of them from writing the same data (ADR-0016, ADR-0028).
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.logging.trace import SOURCE_LIFECYCLE, ExecutionTrace
from tractusx_testlab.models.runtime.results import StepResult, TestResult
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

    __slots__ = ("_last", "_trace")

    def __init__(self, trace: ExecutionTrace | None = None) -> None:
        self._trace = trace
        self._last: dict[str, Any] | None = None

    @property
    def trace(self) -> ExecutionTrace | None:
        return self._trace

    @property
    def last_sequence(self) -> int | None:
        """The ``sequence`` of the event written last, or ``None`` when not tracing."""
        return None if self._last is None else int(self._last["sequence"])

    def envelope(self, event_id: str | None) -> dict[str, Any] | None:
        """The CloudEvent written last, exactly as written, if its id is *event_id*."""
        if event_id is None or self._last is None or self._last["id"] != event_id:
            return None
        return self._last

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
        self._last = envelope
        return str(envelope["id"])

    def run_started(self, job_id: str, tck_id: str) -> str | None:
        return self.emit("tck.start", {"tck_id": tck_id, "run_id": job_id})

    def run_ended(self, job_id: str, status: str, error: str | None = None) -> str | None:
        data: dict[str, Any] = {"status": status, "run_id": job_id}
        if error:
            data["errors"] = [{"code": "RUN_FAILED", "message": error, "retryable": False}]
        return self.emit("tck.end", data)

    def run_held(self, withdrawn: list[str], kept: dict[str, str], occurrence: int) -> str | None:
        """The paused run has stopped: the offers it withdrew, and any it could not."""
        data: dict[str, Any] = {"withdrawn": withdrawn, "occurrence": occurrence}
        if kept:
            data["kept"] = kept
        return self.emit("tck.held", data)

    def run_restored(
        self, restored: list[str], lost: dict[str, str], occurrence: int
    ) -> str | None:
        """The held run goes on: the offers it put back, and any it could not."""
        data: dict[str, Any] = {"restored": restored, "occurrence": occurrence}
        if lost:
            data["lost"] = lost
        return self.emit("tck.restored", data)

    def checkpoints_planned(self, data: dict[str, Any]) -> str | None:
        """Every checkpoint of the run, ``ahead`` (ADR-0028)."""
        return self.emit("checkpoints.planned", data, source=SOURCE_CHECKPOINTS, scope=_PLAN)

    def checkpoint_updated(self, index: int, data: dict[str, Any]) -> str | None:
        """One checkpoint changed; its scope is its place in the plan."""
        return self.emit(
            "checkpoint.updated", data, source=SOURCE_CHECKPOINTS, scope=(*_PLAN, str(index))
        )

    def test_started(self, test: str, index: int, attempt: int = 1) -> str | None:
        data: dict[str, Any] = {"test_id": test, "index": index}
        # Only a run again says so, which keeps a plain run's trace as it was.
        if attempt > 1:
            data["attempt"] = attempt
        return self.emit("tck.test.start", data, scope=(test,))

    def test_awaiting(self, test: str, index: int, occurrence: int = 1) -> str | None:
        data: dict[str, Any] = {"test_id": test, "index": index}
        if occurrence > 1:
            data["occurrence"] = occurrence
        return self.emit("tck.test.awaiting", data, scope=(test,))

    def test_ended(self, result: TestResult, attempt: int = 1) -> str | None:
        test_id = result.test_id or result.test_name
        data = test_data(result)
        if attempt > 1:
            data["attempt"] = attempt
        return self.emit(test_event_type(result.status), data, scope=(test_id,))

    def step_started(
        self,
        test: str,
        step_id: str | None,
        step_index: int,
        step_type: str,
        phase: str,
        inputs: dict[str, Any] | None = None,
        marks: dict[str, Any] | None = None,
    ) -> str | None:
        """The step is about to run, and this is what it is about to be given.

        ``inputs`` is the ``with:`` block with every ``${{ … }}`` reference
        substituted for the value the run seeded or produced. A trace that
        repeated the template instead named the variable and never said what it
        held, which is the one thing the reader opened the trace for. A
        reference that names nothing in scope leaves the block as written; the
        terminal event reports that as the step's failure.
        """
        data: dict[str, Any] = {**_marks(marks), "index": step_index, "phase": phase}
        if inputs:
            data["inputs"] = inputs
        return self.emit(
            "tck.test.step.start",
            data,
            source=step_type,
            scope=(test, phase, step_id or str(step_index)),
        )

    def step_call(
        self,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        index: int,
        call: Any,
        marks: dict[str, Any] | None = None,
    ) -> str | None:
        """One call the step made, published while the step is still running.

        Its path is the step's path plus which call it was, so dropping a phase
        from a trace with a prefix match drops its calls with it — and a step the
        test did not name falls back to what it *is*, which is the only thing
        left to name it by.
        """
        return self.emit(
            "tck.test.step.call",
            {**_marks(marks), **call_data(index, call)},
            source=step_type,
            scope=(*_step_scope(test, phase, step_id, step_type), "calls", str(index)),
        )

    def step_ended(
        self,
        test: str,
        step_id: str | None,
        result: StepResult,
        marks: dict[str, Any] | None = None,
    ) -> str | None:
        """One terminal event carrying the checks, the wire, and the error.

        No separate assertion events: ADR-0016 nests them in ``validations``.
        """
        return self.emit(
            step_event_type(result.status),
            {**step_data(result), **_marks(marks)},
            source=result.step_type,
            scope=(test, result.phase.value.lower(), step_id or result.step_name),
        )

    def step_event(
        self,
        event_type: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        data: dict[str, Any],
        marks: dict[str, Any] | None = None,
    ) -> str | None:
        """A moment of a running step — an address opened, a wait, a question, an answer.

        ``tck.test.step.listening``, ``.waiting``, ``.suspended``, ``.received``,
        ``.selecting`` and ``.selected`` share their path: the step's.
        """
        return self.emit(
            event_type,
            {**_marks(marks), **data},
            source=step_type,
            scope=_step_scope(test, phase, step_id, step_type),
        )


#: ``source`` of the checkpoint events, and the scope their ids start with.
SOURCE_CHECKPOINTS = "testlab/player/checkpoints"
_PLAN = ("checkpoints",)


def _marks(marks: dict[str, Any] | None) -> dict[str, Any]:
    """A step event's marks; a step run outside a frame is the first run of it."""
    return marks or {"attempt": 1}


def _step_scope(test: str, phase: str, step_id: str | None, step_type: str) -> tuple[str, ...]:
    """Where a step's events sit: by its id, else by what it *is*."""
    return (test, phase, step_id or step_type.rsplit("/", 1)[-1])


def received_data(listener: Any, request: Any, waited_ms: int) -> dict[str, Any]:
    """What ``tck.test.step.received`` carries: both halves of the inbound exchange.

    ``request`` is how the system under test called, ``response`` how the Test
    Suite answered it, and ``refused`` why the call was turned away, if it was.
    """
    data: dict[str, Any] = {
        "listener": listener.model_dump(mode="json"),
        "request": {
            "method": request.method,
            "path": request.path,
            "headers": request.headers,
            "query_params": request.query_params,
            "body": request.payload,
        },
        "received_at": request.received_at.isoformat() if request.received_at else None,
        "waited_ms": waited_ms,
    }
    if getattr(request, "response", None) is not None:
        data["response"] = request.response.model_dump(mode="json", exclude_none=True)
    if getattr(request, "refused", None):
        data["refused"] = request.refused
    return data

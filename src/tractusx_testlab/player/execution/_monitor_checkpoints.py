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

"""The checkpoint half of the ExecutionMonitor (ADR-0027).

The run's :class:`~tractusx_testlab.player.checkpoints.CheckpointTracker` is
bound to the monitor, which tells it what happened right after publishing the
event that says so — a test started, a question was asked, answered — and
publishes what it changed: ``checkpoints.planned`` once, then a
``checkpoint.updated`` per change, each straight after its cause.

It also gives every step event its *marks*: which run of the step it is, the
checkpoint it is, and for a question asked again after a pause how many pauses
it has been through — so no two events of a run carry the same data (ADR-0016).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from tractusx_testlab.models.runtime.checkpoint_events import (
    CheckpointsPlannedEvent,
    CheckpointUpdatedEvent,
)
from tractusx_testlab.models.runtime.checkpoints import CheckpointRef, CheckpointStatus
from tractusx_testlab.models.runtime.events import ExecutionEvent
from tractusx_testlab.player.checkpoints import (
    Cause,
    CheckpointPublisher,
    CheckpointTracker,
    current_frame,
)
from tractusx_testlab.player.execution._trace_publisher import TracePublisher


class CheckpointEvents:
    """Following the run's checkpoints, and marking every step event; mixed into the monitor."""

    __slots__ = ()

    _trace: TracePublisher
    _checkpoints: CheckpointTracker | None
    _occurrences: Counter[tuple[str, ...]]

    def _publish(self, event: ExecutionEvent, event_id: str | None = None) -> None:
        raise NotImplementedError

    def checkpoint_publisher(self, job_id: str) -> CheckpointPublisher:
        """Where a tracker of job *job_id* publishes: this monitor."""
        return _JobCheckpoints(self, job_id)

    def on_checkpoints_planned(self, job_id: str, checkpoints: list[CheckpointStatus]) -> None:
        """Every checkpoint the run will meet, each ``ahead``."""
        event = CheckpointsPlannedEvent(job_id=job_id, checkpoints=checkpoints)
        event_id = self._trace.checkpoints_planned(
            {"kind": event.kind.value, "checkpoints": event.checkpoints}
        )
        self._publish(event, event_id)

    def on_checkpoint_updated(
        self,
        job_id: str,
        index: int,
        revision: int,
        cause: Cause | None,
        checkpoint: CheckpointStatus,
    ) -> None:
        """Checkpoint *index* changed, because of *cause*."""
        event = CheckpointUpdatedEvent(
            job_id=job_id,
            index=index,
            revision=revision,
            cause=cause.kind if cause else None,
            cause_sequence=cause.sequence if cause else None,
            checkpoint=checkpoint,
        )
        data: dict[str, Any] = {
            "kind": event.kind.value,
            "index": index,
            "revision": revision,
            "cause": event.cause,
            "cause_sequence": event.cause_sequence,
            "checkpoint": checkpoint,
        }
        self._publish(event, self._trace.checkpoint_updated(index, data))

    # ------------------------------------------------------------------
    # For the rest of the monitor
    # ------------------------------------------------------------------

    def _cause(self, kind: str) -> Cause:
        """The event just published, as the cause of what it changes."""
        return Cause(kind, self._trace.last_sequence)

    def _follow(self, hook: str, *args: Any) -> None:
        """Call the tracker's *hook*, if the run's checkpoints are followed."""
        if self._checkpoints is not None:
            getattr(self._checkpoints, hook)(*args)

    def _marks(self) -> tuple[int, CheckpointRef | None, int]:
        """The running step's attempt, its checkpoint and how many pauses its question had."""
        frame = current_frame()
        if frame is None:
            return 1, None, 0
        ref = self._checkpoints.ref() if self._checkpoints is not None else None
        return frame.attempt, ref, frame.pauses

    def _trace_marks(self, attempt: int, ref: CheckpointRef | None, pauses: int) -> dict[str, Any]:
        """The marks as the trace writes them: ``checkpoint`` and ``pauses`` only when there."""
        marks: dict[str, Any] = {"attempt": attempt}
        if ref is not None:
            marks["checkpoint"] = ref.model_dump(mode="json")
        if pauses:
            marks["pauses"] = pauses
        return marks

    def _occurrence(self, *key: str) -> int:
        """Which time the event named by *key* happens in this run, from 1."""
        self._occurrences[key] += 1
        return self._occurrences[key]


class _JobCheckpoints:
    """A monitor as the publisher of one job's checkpoints."""

    __slots__ = ("_job_id", "_monitor")

    def __init__(self, monitor: CheckpointEvents, job_id: str) -> None:
        self._monitor = monitor
        self._job_id = job_id

    def planned(self, checkpoints: list[CheckpointStatus]) -> None:
        self._monitor.on_checkpoints_planned(self._job_id, checkpoints)

    def updated(
        self, index: int, revision: int, cause: Cause | None, checkpoint: CheckpointStatus
    ) -> None:
        self._monitor.on_checkpoint_updated(self._job_id, index, revision, cause, checkpoint)

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

"""Following a run's checkpoints as it goes — exactly, from where the player stands (ADR-0028).

The engine used to fold its trace back into checkpoint states, matching events
to steps by id and guessing at the rest. The player does not have to guess: it
opens a :class:`~tractusx_testlab.player.checkpoints.frames.StepFrame` for
every step it runs, so it knows which checkpoint a question belongs to, which
run of it this is, whether a repeated question is a new attempt or the same
one resumed after a pause, and how the step ended.

The tracker is told:

* by the phase runner and the step runner, when a step starts and ends
  (:meth:`step`, :meth:`nested`, :meth:`ended`);
* by the monitor, right after it published the event that says so, when a
  test starts or ends, a question is asked, paused or answered, and the run
  ends (:meth:`test_started`, :meth:`asked`, …);
* by ``flow/if``, which branch it did not take (:meth:`not_taken`).

Every change it makes goes out through its publisher at once, so a
``checkpoint.updated`` follows the event that caused it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from tractusx_testlab.authoring._checkpoints import PlannedCheckpoint
from tractusx_testlab.models.primitives.enums import StepStatus, TestStatus
from tractusx_testlab.models.runtime.checkpoints import CheckpointRef, CheckpointStatus
from tractusx_testlab.player.checkpoints import _transitions
from tractusx_testlab.player.checkpoints.frames import (
    StepFrame,
    StepPath,
    current_frame,
    enter,
    leave,
)


@dataclass(frozen=True)
class Cause:
    """The event that changed a checkpoint: its ``kind``, and its ``sequence`` in the trace."""

    kind: str
    sequence: int | None = None


class CheckpointPublisher(Protocol):
    """Where a tracker's events go — the run's monitor."""

    def planned(self, checkpoints: list[CheckpointStatus]) -> None: ...

    def updated(
        self, index: int, revision: int, cause: Cause | None, checkpoint: CheckpointStatus
    ) -> None: ...


class CheckpointTracker:
    """One run's checkpoints and the steps it is running.

    Built empty — it still numbers the runs of each step, and publishes
    nothing — for a context made outside the player; the player builds one
    with the run's plan and publisher (:meth:`for_run`).
    """

    __slots__ = ("_cancelled", "_planned", "_publisher", "_revisions", "_runs", "_statuses")

    def __init__(
        self,
        planned: list[PlannedCheckpoint] | None = None,
        publisher: CheckpointPublisher | None = None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> None:
        self._planned = list(planned or [])
        self._statuses = [CheckpointStatus(**item.entry.model_dump()) for item in self._planned]
        self._revisions = [0] * len(self._planned)
        self._publisher = publisher
        self._cancelled = cancelled
        self._runs: Counter[tuple[str, StepPath]] = Counter()

    @property
    def checkpoints(self) -> list[CheckpointStatus]:
        """Every checkpoint of the run as it stands, in plan order."""
        return list(self._statuses)

    def plan(self) -> None:
        """Publish the plan: every checkpoint, ``ahead``. Once, before the first test."""
        if self._publisher is not None and self._planned:
            self._publisher.planned(list(self._statuses))

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    @contextmanager
    def step(self, test_id: str, path: StepPath) -> Iterator[StepFrame]:
        """Run the step at *path* of *test_id* in a frame of its own."""
        self._runs[(test_id, path)] += 1
        frame = StepFrame(test_id, path, self._runs[(test_id, path)])
        frame.checkpoint = next(
            (i for i, item in enumerate(self._planned) if self._at(item, test_id, path)), None
        )
        if frame.checkpoint is not None:
            frame.checkpoint_attempt = self._statuses[frame.checkpoint].attempts + 1
        token = enter(frame)
        try:
            yield frame
        finally:
            leave(token)
            if not frame.ended:  # interrupted: cancelled, or an error past the step's guard
                self._end(frame, None, None)

    @contextmanager
    def nested(self, at: tuple[str, int] | None) -> Iterator[StepFrame | None]:
        """Run a step a flow step carries, *at* its ``with:`` key and index, in a frame of its own."""
        parent = current_frame()
        if at is None or parent is None:
            yield None
            return
        with self.step(parent.test_id, (*parent.path, *at)) as frame:
            self.begin()
            yield frame

    def begin(self) -> None:
        """The current step has started: a checkpoint it does not ask for itself is asked now."""
        frame = current_frame()
        if frame is None or frame.checkpoint is None or self._planned[frame.checkpoint].asks:
            return
        self._ask(frame, None)

    def ended(self, outcome: StepStatus, cause: Cause | None = None) -> None:
        """The current step ended with *outcome*."""
        frame = current_frame()
        if frame is not None and not frame.ended:
            self._end(frame, outcome, cause)

    def not_taken(self, branch: str) -> None:
        """The current flow step did not take *branch*: what it carries is not needed."""
        frame = current_frame()
        if frame is None:
            return
        prefix = (*frame.path, branch)
        for index in self._under(frame.test_id, prefix):
            if self._statuses[index].state == "ahead":
                self._set(index, None, state="skipped")

    # ------------------------------------------------------------------
    # Questions
    # ------------------------------------------------------------------

    def asked(self, cause: Cause) -> None:
        """The current step asked (``step_waiting``, ``step_selecting``); again after a pause."""
        frame = current_frame()
        if frame is not None and frame.checkpoint is not None and not frame.asked:
            self._ask(frame, cause)

    def suspended(self) -> None:
        """The current step's question was paused; the next ask resumes it."""
        frame = current_frame()
        if frame is not None:
            frame.pauses += 1

    def answered(self, cause: Cause, waited_ms: int) -> None:
        """The current step's question was answered, after *waited_ms* of it being open."""
        frame = current_frame()
        if frame is None or frame.checkpoint is None:
            return
        if not frame.asked:  # answered at once, before anything was announced
            self._ask(frame, cause)
        frame.answered = True
        self._set(
            frame.checkpoint,
            cause,
            state="cleared",
            answered_at=datetime.now(UTC),
            response_s=round(waited_ms / 1000, 3),
        )

    def ref(self) -> CheckpointRef | None:
        """Which checkpoint, and which attempt of it, the current step is — for its events."""
        frame = current_frame()
        if frame is None or frame.checkpoint is None:
            return None
        entry = self._statuses[frame.checkpoint]
        return CheckpointRef(
            index=frame.checkpoint, attempt=frame.checkpoint_attempt, direction=entry.direction
        )

    # ------------------------------------------------------------------
    # Tests and the run
    # ------------------------------------------------------------------

    def test_started(self, test_id: str, cause: Cause) -> None:
        """*test_id* starts, again maybe: its checkpoints start over; their attempts go on."""
        for index in self._under(test_id, ()):
            self._set(index, cause, state="ahead", asked_at=None, answered_at=None, response_s=None)

    def test_ended(self, test_id: str, outcome: TestStatus, cause: Cause) -> None:
        """*test_id* ended: what it did not reach is ``skipped`` or ``not_reached``."""
        for index in self._under(test_id, ()):
            state = _transitions.test_ended(self._statuses[index].state, outcome, self._cancelled())
            if state is not None:
                self._set(index, cause, state=state)

    def job_ended(self, cause: Cause) -> None:
        """The run ended: whatever is still ``ahead`` or ``now`` is ``not_reached``."""
        for index, status in enumerate(self._statuses):
            if status.state in _transitions.OPEN:
                self._set(index, cause, state="not_reached")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ask(self, frame: StepFrame, cause: Cause | None) -> None:
        if frame.checkpoint is None:
            return
        frame.asked = True
        self._set(
            frame.checkpoint,
            cause,
            state="now",
            attempts=frame.checkpoint_attempt,
            asked_at=datetime.now(UTC),
            answered_at=None,
            response_s=None,
        )

    def _end(self, frame: StepFrame, outcome: StepStatus | None, cause: Cause | None) -> None:
        frame.ended = True
        at = datetime.now(UTC)
        if frame.checkpoint is not None:
            changes = _transitions.own_step_ended(
                self._statuses[frame.checkpoint],
                frame,
                outcome,
                asks=self._planned[frame.checkpoint].asks,
                cancelled=self._cancelled(),
                at=at,
            )
            self._set(frame.checkpoint, cause, **changes)
        for index in self._under(frame.test_id, frame.path):
            if index != frame.checkpoint and self._statuses[index].state in _transitions.OPEN:
                self._set(index, cause, state=_transitions.carried_step_ended(outcome))

    def _under(self, test_id: str, prefix: StepPath) -> list[int]:
        """The checkpoints of *test_id* whose step sits at or under *prefix*."""
        return [
            index
            for index, item in enumerate(self._planned)
            if item.entry.test_id == test_id and item.path[: len(prefix)] == prefix
        ]

    @staticmethod
    def _at(item: PlannedCheckpoint, test_id: str, path: StepPath) -> bool:
        return item.entry.test_id == test_id and item.path == path

    def _set(self, index: int, cause: Cause | None, **changes: Any) -> None:
        """Apply *changes* to checkpoint *index*, and publish it if it changed."""
        before = self._statuses[index]
        after = before.model_copy(update=changes)
        if after == before:
            return
        self._statuses[index] = after
        self._revisions[index] += 1
        if self._publisher is not None:
            self._publisher.updated(index, self._revisions[index], cause, after)

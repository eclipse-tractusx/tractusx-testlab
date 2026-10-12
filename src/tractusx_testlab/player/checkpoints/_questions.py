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

"""The moments of a checkpoint's question: asked, paused, answered, turned away (ADR-0028).

Half of :class:`~tractusx_testlab.player.checkpoints.tracker.CheckpointTracker`,
kept apart so the tracker reads as steps and tests: the monitor calls these
right after it published the event that says so, for the step the calling
coroutine runs (its :class:`~tractusx_testlab.player.checkpoints.frames.StepFrame`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tractusx_testlab.models.runtime.checkpoints import CheckpointRef, CheckpointStatus
from tractusx_testlab.player.checkpoints.frames import StepFrame, current_frame


@dataclass(frozen=True)
class Cause:
    """The event that changed a checkpoint: its ``kind``, and its ``sequence`` in the trace."""

    kind: str
    sequence: int | None = None


class QuestionHooks:
    """The question half of the tracker; mixed into ``CheckpointTracker``."""

    __slots__ = ()

    _statuses: list[CheckpointStatus]

    def _ask(self, frame: StepFrame, cause: Cause | None) -> None:
        raise NotImplementedError

    def _set(self, index: int, cause: Cause | None, **changes: Any) -> None:
        raise NotImplementedError

    def asked(self, cause: Cause) -> None:
        """The current step asked (``step_waiting``, ``step_selecting``); again after a pause.

        Noted on the frame for a step that is no checkpoint too: a question put
        again is a pause resumed, and its ``pauses`` count either way.
        """
        frame = current_frame()
        if frame is None or frame.asked:
            return
        if frame.checkpoint is None:
            frame.asked = True
        else:
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

    def refused(self, cause: Cause) -> None:
        """A call came to the current step's question and was turned away (no key, the wrong one).

        It is not an answer: the checkpoint is not ``cleared``, and stays
        ``now`` until the step fails on it — ``failed``, the call having come.
        """
        frame = current_frame()
        if frame is None or frame.checkpoint is None:
            return
        if not frame.asked:
            self._ask(frame, cause)
        frame.answered = True

    def ref(self) -> CheckpointRef | None:
        """Which checkpoint, and which attempt of it, the current step is — for its events."""
        frame = current_frame()
        if frame is None or frame.checkpoint is None:
            return None
        entry = self._statuses[frame.checkpoint]
        return CheckpointRef(
            index=frame.checkpoint, attempt=frame.checkpoint_attempt, direction=entry.direction
        )

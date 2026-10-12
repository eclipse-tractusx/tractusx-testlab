################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The checkpoint state machine, step by step (ADR-0028).

The tracker is driven here the way the runner and the monitor drive it — a
frame per step, the hooks in the order the events go out — with a publisher
that records what it is given.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tractusx_testlab.authoring._checkpoints import PlannedCheckpoint
from tractusx_testlab.models.primitives.checkpoint import Direction
from tractusx_testlab.models.primitives.enums import StepStatus, TestStatus
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry, CheckpointStatus
from tractusx_testlab.player.checkpoints import Cause, CheckpointTracker, current_frame


class _Published:
    def __init__(self) -> None:
        self.plans: list[list[CheckpointStatus]] = []
        self.updates: list[tuple[int, int, Cause | None, CheckpointStatus]] = []

    def planned(self, checkpoints: list[CheckpointStatus]) -> None:
        self.plans.append(checkpoints)

    def updated(self, index: int, revision: int, cause: Any, checkpoint: CheckpointStatus) -> None:
        self.updates.append((index, revision, cause, checkpoint))

    def states(self, index: int = 0) -> list[str]:
        return [u[3].state for u in self.updates if u[0] == index]


def _planned(
    path: tuple, direction: Direction = Direction.INBOUND, *, asks: bool = True, test: str = "t"
) -> PlannedCheckpoint:
    entry = CheckpointEntry(
        test_id=test,
        test_name=test,
        phase=str(path[0]),
        position="/".join(map(str, path)),
        uses="mock/wait/http_request",
        direction=direction,
        kind="select" if direction is Direction.INTERNAL else "wait",
    )
    return PlannedCheckpoint(entry=entry, path=path, asks=asks)


def _tracker(*planned: PlannedCheckpoint, cancelled: bool = False):
    published = _Published()
    return CheckpointTracker(list(planned), published, lambda: cancelled), published


_ASKED, _ANSWERED = Cause("step_waiting", 7), Cause("step_received", 8)


def test_the_plan_goes_out_once_each_ahead() -> None:
    tracker, published = _tracker(_planned(("execution", 0)))
    tracker.plan()
    assert [[c.state for c in plan] for plan in published.plans] == [["ahead"]]


def test_a_run_without_checkpoints_publishes_no_plan() -> None:
    tracker, published = _tracker()
    tracker.plan()
    assert published.plans == []


def test_an_ask_and_its_answer_name_their_cause_and_count_one_attempt() -> None:
    tracker, published = _tracker(_planned(("execution", 0)))
    with tracker.step("t", ("execution", 0)):
        tracker.asked(_ASKED)
        tracker.asked(_ASKED)  # again after a pause: the same attempt
        tracker.answered(_ANSWERED, waited_ms=1500)
        tracker.ended(StepStatus.PASSED, Cause("step_completed", 9))
    assert published.states() == ["now", "cleared"]
    assert [u[2] for u in published.updates] == [_ASKED, _ANSWERED]
    assert [u[1] for u in published.updates] == [1, 2]
    final = published.updates[-1][3]
    assert (final.attempts, final.response_s) == (1, 1.5)


def test_a_step_that_ends_without_an_answer_times_its_question_out() -> None:
    tracker, published = _tracker(_planned(("execution", 0)))
    with tracker.step("t", ("execution", 0)):
        tracker.asked(_ASKED)
        tracker.ended(StepStatus.FAILED)
    assert published.states() == ["now", "timed_out"]


def test_a_step_that_fails_after_its_answer_fails_its_checkpoint() -> None:
    tracker, published = _tracker(_planned(("execution", 0)))
    with tracker.step("t", ("execution", 0)):
        tracker.asked(_ASKED)
        tracker.answered(_ANSWERED, 10)
        tracker.ended(StepStatus.FAILED)
    assert published.states() == ["now", "cleared", "failed"]


def test_a_cancelled_run_leaves_an_open_question_not_reached() -> None:
    tracker, published = _tracker(_planned(("execution", 0)), cancelled=True)
    with tracker.step("t", ("execution", 0)):
        tracker.asked(_ASKED)
        tracker.ended(StepStatus.FAILED)
    assert published.states() == ["now", "not_reached"]


def test_a_step_interrupted_without_an_outcome_is_not_reached() -> None:
    tracker, published = _tracker(_planned(("execution", 0)))
    with pytest.raises(asyncio.CancelledError), tracker.step("t", ("execution", 0)):
        tracker.asked(_ASKED)
        raise asyncio.CancelledError
    assert published.states() == ["now", "not_reached"]


def test_a_checkpoint_its_step_does_not_ask_is_now_while_the_step_runs() -> None:
    tracker, published = _tracker(_planned(("execution", 0), Direction.OUTBOUND, asks=False))
    with tracker.step("t", ("execution", 0)):
        tracker.begin()
        tracker.ended(StepStatus.FAILED)
    assert published.states() == ["now", "failed"]


def test_a_choice_taken_without_asking_is_skipped() -> None:
    tracker, published = _tracker(_planned(("execution", 0), Direction.INTERNAL))
    with tracker.step("t", ("execution", 0)):
        tracker.ended(StepStatus.PASSED)
    assert published.states() == ["skipped"]


def test_a_nested_step_runs_in_its_own_frame_and_counts_its_runs() -> None:
    nested = _planned(("execution", 0, "steps", 0))
    tracker, published = _tracker(nested)
    with tracker.step("t", ("execution", 0)):
        for _ in range(2):
            with tracker.nested(("steps", 0)) as frame:
                assert frame is not None and frame.path == ("execution", 0, "steps", 0)
                tracker.asked(_ASKED)
                tracker.ended(StepStatus.FAILED)
        assert current_frame().path == ("execution", 0)
        tracker.ended(StepStatus.FAILED)
    assert published.states() == ["now", "timed_out", "now", "timed_out"]
    assert published.updates[-1][3].attempts == 2


def test_a_branch_not_taken_is_skipped_and_one_never_reached_follows_its_flow_step() -> None:
    then, other = _planned(("execution", 0, "then", 0)), _planned(("execution", 0, "else", 0))
    tracker, published = _tracker(then, other)
    with tracker.step("t", ("execution", 0)):
        tracker.not_taken("then")
        tracker.ended(StepStatus.FAILED)
    assert (published.states(0), published.states(1)) == (["skipped"], ["not_reached"])


def test_a_test_started_again_starts_its_checkpoints_over_and_keeps_counting() -> None:
    tracker, published = _tracker(_planned(("execution", 0)))
    for _ in range(2):
        tracker.test_started("t", Cause("test_started"))
        with tracker.step("t", ("execution", 0)):
            tracker.asked(_ASKED)
            tracker.answered(_ANSWERED, 1)
            tracker.ended(StepStatus.PASSED)
    assert published.states() == ["now", "cleared", "ahead", "now", "cleared"]
    assert published.updates[-1][3].attempts == 2


@pytest.mark.parametrize(
    ("outcome", "cancelled", "state"),
    [
        (TestStatus.COMPLETED, False, "skipped"),
        (TestStatus.FAILED, False, "not_reached"),
        (TestStatus.SKIPPED, True, "not_reached"),
    ],
)
def test_a_test_that_ends_without_reaching_one_skips_it_or_leaves_it(
    outcome: TestStatus, cancelled: bool, state: str
) -> None:
    tracker, published = _tracker(_planned(("execution", 0)), cancelled=cancelled)
    tracker.test_ended("t", outcome, Cause("test_completed"))
    assert published.states() == [state]


def test_the_end_of_the_run_leaves_nothing_open() -> None:
    tracker, _ = _tracker(_planned(("execution", 0)), _planned(("execution", 1)))
    with tracker.step("t", ("execution", 0)):
        tracker.asked(_ASKED)
    tracker.job_ended(Cause("job_failed"))
    assert {c.state for c in tracker.checkpoints} == {"not_reached"}


def test_a_step_names_the_checkpoint_and_attempt_its_events_belong_to() -> None:
    tracker, _ = _tracker(_planned(("execution", 1)))
    with tracker.step("t", ("execution", 0)):
        assert tracker.ref() is None
    with tracker.step("t", ("execution", 1)):
        ref = tracker.ref()
    assert ref is not None and (ref.index, ref.attempt, ref.direction) == (0, 1, "inbound")


def test_an_unbound_tracker_numbers_runs_and_publishes_nothing() -> None:
    tracker = CheckpointTracker()
    for attempt in (1, 2):
        with tracker.step("t", ("setup", 0)) as frame:
            assert frame.attempt == attempt
            tracker.asked(_ASKED)
    assert tracker.checkpoints == []

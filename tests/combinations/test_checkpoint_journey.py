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

"""A real run of a TCK of checkpoints: what the player says about each, and when (ADR-0028).

Compiled and loaded the way an operator's TCK is, run by the player with its
own mock server, answered by a system under test and an operator acting on the
run's own events (``checkpoint_tck.Answers``). The ``choice`` test is run a
second time, as a session can, to see a test restart.
"""

from __future__ import annotations

from pathlib import Path

from combinations.checkpoint_tck import Run
from tractusx_testlab.player.loading.loader import Loader


class TestThePlan:
    def test_it_goes_out_once_after_the_job_started_and_before_any_test(
        self, checkpoint_run: Run
    ) -> None:
        kinds = [payload["kind"] for _, payload in checkpoint_run.answers.events]
        assert kinds.count("checkpoints_planned") == 1
        assert kinds.index("job_started") < kinds.index("checkpoints_planned")
        assert kinds.index("checkpoints_planned") < kinds.index("test_started")

    def test_it_lists_every_checkpoint_in_run_order_each_ahead(self, checkpoint_run: Run) -> None:
        assert [(p["test_id"], p["step_id"]) for p in checkpoint_run.planned()] == [
            ("wait-answered", "await_call"),
            ("wait-silent", "await_silence"),
            ("choice", "pick"),
            ("branch", "never"),
            ("branch", "note"),
            ("retry", "await_again"),
            ("paused", "await_held"),
            ("marked", "announce"),
            ("cancel", "abandoned"),
        ]
        assert {p["state"] for p in checkpoint_run.planned()} == {"ahead"}

    def test_it_is_the_inspection_of_the_package(
        self, checkpoint_run: Run, checkpoint_package: Path
    ) -> None:
        inspected = [
            entry.model_dump(mode="json")
            for entry in Loader().load(checkpoint_package).checkpoints()
        ]
        fields = set(inspected[0])
        assert [{k: p[k] for k in fields} for p in checkpoint_run.planned()] == inspected

    def test_it_says_where_each_one_sits_and_how_it_may_go(self, checkpoint_run: Run) -> None:
        by_step = {p["step_id"]: p for p in checkpoint_run.planned()}
        assert by_step["await_call"]["label"] == "Push the certificate"
        assert (by_step["await_call"]["direction"], by_step["await_call"]["kind"]) == (
            "inbound",
            "wait",
        )
        assert (by_step["pick"]["direction"], by_step["pick"]["kind"]) == ("internal", "select")
        assert by_step["never"]["conditional"] and by_step["never"]["position"] == (
            "execution/0/then/0"
        )
        assert by_step["await_again"]["repeated"] and not by_step["await_again"]["conditional"]
        assert by_step["note"]["direction"] == "outbound"
        assert by_step["announce"]["description"] == "The run says hello"


class TestTheStates:
    def test_a_wait_answered_is_now_then_cleared(self, checkpoint_run: Run) -> None:
        assert checkpoint_run.states("await_call") == ["now", "cleared"]
        final = checkpoint_run.final("await_call")
        assert final["attempts"] == 1 and final["response_s"] is not None

    def test_a_wait_nobody_answers_times_out(self, checkpoint_run: Run) -> None:
        assert checkpoint_run.states("await_silence") == ["now", "timed_out"]

    def test_a_choice_is_cleared_and_a_restart_asks_it_again(self, checkpoint_run: Run) -> None:
        assert checkpoint_run.states("pick") == ["now", "cleared", "ahead", "now", "cleared"]
        assert [u["checkpoint"]["attempts"] for u in checkpoint_run.updates("pick")] == [
            1,
            1,
            1,
            2,
            2,
        ]

    def test_a_branch_not_taken_is_skipped_and_a_marked_step_in_the_other_clears(
        self, checkpoint_run: Run
    ) -> None:
        assert checkpoint_run.states("never") == ["skipped"]
        assert checkpoint_run.states("note") == ["now", "cleared"]

    def test_a_retry_asks_again_as_a_new_attempt(self, checkpoint_run: Run) -> None:
        assert checkpoint_run.states("await_again") == ["now", "timed_out", "now", "cleared"]
        assert checkpoint_run.final("await_again")["attempts"] == 2

    def test_a_question_paused_twice_is_one_attempt(self, checkpoint_run: Run) -> None:
        assert checkpoint_run.states("await_held") == ["now", "cleared"]
        waits = [
            w for w in checkpoint_run.answers.of("step.waiting") if w["step_id"] == "await_held"
        ]
        assert [w["pauses"] for w in waits] == [0, 1, 2]
        assert {w["checkpoint"]["attempt"] for w in waits} == {1}

    def test_a_step_marked_in_yaml_is_now_while_it_runs_and_one_switched_off_is_none(
        self, checkpoint_run: Run
    ) -> None:
        assert checkpoint_run.states("announce") == ["now", "cleared"]
        assert "only" not in [p["step_id"] for p in checkpoint_run.planned()]

    def test_a_choice_the_run_is_cancelled_at_is_not_reached(self, checkpoint_run: Run) -> None:
        assert checkpoint_run.states("abandoned") == ["now", "not_reached"]

    def test_a_run_its_host_cancelled_ends_cancelled(self, checkpoint_run: Run) -> None:
        assert len(checkpoint_run.answers.of("job.cancelled")) == 1
        assert not checkpoint_run.answers.of("job.failed") and not checkpoint_run.answers.of(
            "job.completed"
        )
        (end,) = [e for e in checkpoint_run.trace if e["type"] == "tck.end"]
        assert end["data"]["status"] == "CANCELLED"

    def test_every_update_follows_its_cause_and_says_which_it_was(
        self, checkpoint_run: Run
    ) -> None:
        trace = checkpoint_run.trace
        by_sequence = {event["sequence"]: event for event in trace}
        for event in trace:
            if event["type"] != "checkpoint.updated" or event["data"].get("cause_sequence") is None:
                continue
            cause = by_sequence[event["data"]["cause_sequence"]]
            assert cause["sequence"] < event["sequence"]
            between = trace[cause["sequence"] : event["sequence"] - 1]
            assert {e["type"] for e in between} <= {"checkpoint.updated"}


class TestTheExchanges:
    def test_the_call_that_cleared_an_inbound_checkpoint_names_it_with_its_answer(
        self, checkpoint_run: Run
    ) -> None:
        index = checkpoint_run.index("await_call")
        (received,) = [
            event
            for event in checkpoint_run.trace
            if event["type"] == "tck.test.step.received"
            and event["data"]["checkpoint"]["index"] == index
        ]
        assert received["data"]["checkpoint"] == {
            "index": index,
            "attempt": 1,
            "direction": "inbound",
        }
        assert received["data"]["response"] == {"status_code": 202, "body": {"ok": 1}}
        assert received["data"]["request"]["body"] == {"cert": 1}

    def test_what_was_offered_and_what_was_chosen_name_the_checkpoint(
        self, checkpoint_run: Run
    ) -> None:
        index = checkpoint_run.index("pick")
        offered = [e for e in checkpoint_run.trace if e["type"] == "tck.test.step.selecting"]
        chosen = [e for e in checkpoint_run.trace if e["type"] == "tck.test.step.selected"]
        picks = [e for e in offered + chosen if e["data"]["checkpoint"]["index"] == index]
        assert sorted(e["data"]["checkpoint"]["attempt"] for e in picks) == [1, 1, 2, 2]
        assert {e["data"]["value"] for e in chosen if e in picks} == {"beta"}

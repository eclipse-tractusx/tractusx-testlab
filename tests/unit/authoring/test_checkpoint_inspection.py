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

"""A package's checkpoints, read without running it (ADR-0027, ADR-0022).

``Tck.checkpoints()`` is what the engine's briefing lists before a run, and
what the run's ``checkpoints.planned`` carries: the declarations on the step
types, the test's ``checkpoint:`` marks, nested steps in their flow steps.
"""

from __future__ import annotations

from typing import Any

import pytest

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.models import StepDefinition, TestDefinition
from tractusx_testlab.models.primitives.checkpoint import Checkpoint, Direction, Via


def _tck(*steps: dict[str, Any], test_id: str = "t") -> Tck:
    test = TestDefinition.model_validate(
        {
            "syntax": "v1-alpha",
            "id": test_id,
            "namespace": "n",
            "metadata": {"name": "The test", "version": "1"},
            "execution": list(steps),
        }
    )
    return Tck.from_single_test(test)


def _wait(step_id: str = "await", **extra: Any) -> dict:
    return {"id": step_id, "uses": "mock/wait/http_request", "with": {"mock": "x", **extra}}


def _select(step_id: str = "pick", **extra: Any) -> dict:
    return {"id": step_id, "uses": "flow/select", "with": {"options": ["a", "b"], **extra}}


class TestTheDeclarations:
    def test_the_step_types_that_ask_someone_declare_it_on_their_decorator(self) -> None:
        import tractusx_testlab.steps  # noqa: F401 — registers them

        declared = {
            step_type: StepRegistry.get_any(step_type).checkpoint
            for step_type in StepRegistry.list_step_types()
            if StepRegistry.get_any(step_type).checkpoint is not None
        }
        assert declared == {
            "mock/wait/http_request": Checkpoint(direction=Direction.INBOUND),
            "mock/wait/dataplane/http_request": Checkpoint(
                direction=Direction.INBOUND, via=Via.DATAPLANE
            ),
            "notification/consumer/send": Checkpoint(
                direction=Direction.OUTBOUND, via=Via.DATAPLANE
            ),
            "flow/select": Checkpoint(direction=Direction.INTERNAL),
            "connector/datasets/select": Checkpoint(direction=Direction.INTERNAL),
        }

    @pytest.mark.parametrize(
        ("direction", "kind"),
        [(Direction.INBOUND, "wait"), (Direction.OUTBOUND, "wait"), (Direction.INTERNAL, "select")],
    )
    def test_the_engines_kind_follows_the_direction(self, direction: Direction, kind: str) -> None:
        assert Checkpoint(direction=direction).kind == kind

    def test_an_inbound_call_is_direct_unless_said_and_an_internal_one_travels_nowhere(
        self,
    ) -> None:
        assert Checkpoint(direction=Direction.INBOUND).via is Via.DIRECT
        assert Checkpoint(direction=Direction.OUTBOUND).via is None
        with pytest.raises(ValueError, match="calls nothing"):
            Checkpoint(direction=Direction.INTERNAL, via=Via.DIRECT)

    def test_the_step_contract_says_it(self) -> None:
        import tractusx_testlab.steps  # noqa: F401 — registers them

        contract = StepRegistry.get_any("flow/select").describe()
        assert contract.model_dump(exclude_none=True)["checkpoint"] == {"direction": "internal"}
        assert StepRegistry.get_any("util/log").describe().checkpoint is None


class TestTheList:
    def test_each_declared_step_is_an_entry_with_what_the_briefing_shows(self) -> None:
        (entry,) = _tck(_wait(action={"label": "Push it", "description": "Now"})).checkpoints()
        assert entry.model_dump(mode="json") == {
            "test_id": "t",
            "test_name": "The test",
            "phase": "execution",
            "position": "execution/0",
            "step_id": "await",
            "uses": "mock/wait/http_request",
            "direction": "inbound",
            "kind": "wait",
            "via": "direct",
            "name": None,
            "label": "Push it",
            "description": "Now",
            "timeout_s": 30,  # the step's default
            "conditional": False,
            "repeated": False,
        }

    def test_a_flow_steps_nested_steps_are_walked_and_flagged(self) -> None:
        tck = _tck(
            {
                "id": "decide",
                "uses": "flow/if",
                "with": {
                    "conditions": [{"input": 1}],
                    "then": [{"uses": "flow/retry", "with": {"steps": [_wait()]}}],
                    "else": [_select()],
                },
            }
        )
        entries = {e.step_id: e for e in tck.checkpoints()}
        assert entries["await"].position == "execution/0/then/0/steps/0"
        assert (entries["await"].conditional, entries["await"].repeated) == (True, True)
        assert (entries["pick"].conditional, entries["pick"].repeated) == (True, False)

    def test_a_test_marks_any_step_or_switches_one_off(self) -> None:
        tck = _tck(
            {"id": "note", "uses": "util/log", "with": {"message": "m"}, "checkpoint": True},
            {**_select(), "checkpoint": False},
            {
                "id": "push",
                "uses": "http/http_request",
                "with": {"url": "http://x"},
                "checkpoint": {"label": "Pushed", "direction": "outbound", "via": "dataplane"},
            },
            {**_wait(), "checkpoint": {"label": "Mine"}},
        )
        entries = [(e.step_id, e.direction, e.via, e.label) for e in tck.checkpoints()]
        assert entries == [
            ("note", "outbound", None, None),
            ("push", "outbound", "dataplane", "Pushed"),
            ("await", "inbound", "direct", "Mine"),
        ]

    def test_text_still_holding_a_template_is_left_out(self) -> None:
        (entry,) = _tck(
            _wait(action={"label": "${{ env.x }}"}, timeout_s="${{ env.t }}")
        ).checkpoints()
        assert (entry.label, entry.timeout_s) == (None, None)

    def test_the_tests_a_run_skips_are_left_out_by_entry_or_by_id(self) -> None:
        tck = _tck(_wait(), test_id="skipped")
        assert tck.checkpoints(["skipped"]) == ()
        assert len(tck.checkpoints()) == 1

    def test_a_step_that_is_not_one_is_none(self) -> None:
        assert _tck({"uses": "util/log", "with": {"message": "m"}}).checkpoints() == ()
        assert StepDefinition(uses="util/log").checkpoint is None

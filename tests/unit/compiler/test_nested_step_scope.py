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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A step nested in a flow step is in scope under its id, as a top-level one is.

The runner publishes a nested step's ``returns:`` under its phase, so the
compiler has to know those ids too: the data-plane call in a ``flow/retry``
reads the EDR the negotiation before it returned, and was refused for naming
nothing the TCK supplies.
"""

from __future__ import annotations

from tractusx_testlab.compiler.validation.validator import TestValidator, _scope_of
from tractusx_testlab.models import StepDefinition, TestDefinition
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition


def _mint(step_id: str) -> dict:
    return {"id": step_id, "uses": "util/generate_uuid", "returns": {"value": {"type": "string"}}}


def _log(value: str) -> dict:
    return {"id": "echo", "uses": "util/log", "with": {"message": "m", "value": value}}


def _errors(*steps: StepDefinition, phase: str = "execution") -> list[str]:
    test = TestDefinition(
        syntax="v1-alpha",
        kind="test",
        id="t",
        namespace="n",
        metadata={"name": "t"},
        **{phase: list(steps)},
    )
    tck = TckDefinition(
        kind="tck",
        syntax="v1-alpha",
        id="tck",
        metadata=TckMetadataDefinition(name="tck", version="1.0"),
    )
    result = TestValidator().validate(test, scope=_scope_of(tck, test))
    return [issue.message for issue in result.issues if issue.level == "error"]


def _retry(*steps: dict) -> StepDefinition:
    return StepDefinition(id="attempt", uses="flow/retry", with_={"steps": list(steps)})


class TestNestedStepIds:
    def test_a_retried_step_reads_the_one_before_it(self) -> None:
        assert _errors(_retry(_mint("mint"), _log("${{ execution.mint.value }}"))) == []

    def test_a_top_level_step_reads_a_nested_one(self) -> None:
        after = StepDefinition(
            id="after",
            uses="util/log",
            with_={"message": "m", "value": "${{ execution.mint.value }}"},
        )
        assert _errors(_retry(_mint("mint")), after) == []

    def test_a_step_nested_two_deep_is_in_scope(self) -> None:
        branch = {
            "id": "branch",
            "uses": "flow/if",
            "with": {
                "conditions": [{"input": "go", "operator": "not_null"}],
                "then": [_mint("deep")],
            },
        }
        assert _errors(_retry(branch, _log("${{ execution.deep.value }}"))) == []

    def test_a_nested_id_is_in_scope_under_its_own_phase_only(self) -> None:
        (error,) = _errors(
            _retry(_mint("mint"), _log("${{ execution.mint.value }}")), phase="teardown"
        )
        assert "execution.mint.value" in error

    def test_an_id_no_step_has_is_still_refused(self) -> None:
        (error,) = _errors(_retry(_mint("mint"), _log("${{ execution.nope.value }}")))
        assert "execution.nope.value" in error

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""A step's ``if:`` must be an expression the run evaluates as written.

Until this check existed ``if:`` compiled whatever it said. An expression the
evaluator did not recognise ran its step; a variable name with a typo read as
empty and skipped it; an ``if:`` in teardown or on a nested step was never read.
"""

from __future__ import annotations

from typing import Any

import pytest

from tractusx_testlab.compiler.validation.validator import TestValidator, _scope_of
from tractusx_testlab.models import StepDefinition, TestDefinition
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition

_EXTRACT = StepDefinition(
    id="first_status",
    uses="util/json_path_extract",
    with_={"input": {"a": "b"}, "path": "a"},
    returns={"value": {"type": "string"}},
)


def _gated(condition: str, step_id: str = "gated") -> StepDefinition:
    return StepDefinition.model_validate(
        {"id": step_id, "uses": "util/log", "with": {"message": "m"}, "if": condition}
    )


def _test(**phases: list[StepDefinition]) -> TestDefinition:
    return TestDefinition(
        syntax="v1-alpha", kind="test", id="t", namespace="n", metadata={"name": "t"}, **phases
    )


def _errors(test: TestDefinition, env: tuple[str, ...] = ("region",)) -> list[Any]:
    tck = TckDefinition(
        kind="tck",
        syntax="v1-alpha",
        id="tck",
        metadata=TckMetadataDefinition(name="tck", version="1.0"),
    )
    scope = _scope_of(tck, test) | {f"env.{name}" for name in env}
    issues = TestValidator().validate(test, scope=scope).issues
    return [issue for issue in issues if issue.level == "error"]


def _messages(condition: str) -> list[str]:
    return [issue.message for issue in _errors(_test(execution=[_EXTRACT, _gated(condition)]))]


class TestTheGrammarIsChecked:
    @pytest.mark.parametrize(
        "condition",
        [
            "${{ success() }}",
            "failure()",
            "${{ always() }}",
            "${{ steps.first_status.outcome == 'success' }}",
            "${{ steps.first_status.outcome != 'skipped' }}",
            "${{ vars.execution.first_status.value == 'RECEIVED' }}",
            "${{ vars.execution.first_status.value != RECEIVED }}",
            "${{ vars.execution.first_status.value }}",
            "${{ vars.region == 'eu' }}",
            "${{ vars.value == 'RECEIVED' }}",
            "${{ vars.execution.id }}",
        ],
    )
    def test_an_expression_the_run_evaluates_compiles(self, condition: str) -> None:
        assert _messages(condition) == []

    @pytest.mark.parametrize(
        "condition",
        [
            "${{ vars.region == 'eu' and success() }}",
            "${{ !success() }}",
            "${{ execution.first_status.value == 'RECEIVED' }}",
            "${{ vars.region === 'eu' }}",
        ],
    )
    def test_an_expression_outside_the_grammar_is_refused(self, condition: str) -> None:
        messages = _messages(condition)
        assert len(messages) == 1
        assert "is not an expression testlab evaluates" in messages[0]

    def test_the_retired_spelling_is_refused_with_the_new_one(self) -> None:
        messages = _messages("${region} == 'eu'")
        assert len(messages) == 1
        assert "vars.region" in messages[0]

    def test_the_finding_is_located_on_the_step_and_its_if(self) -> None:
        [issue] = _errors(_test(execution=[_EXTRACT, _gated("nonsense")]))
        assert (issue.phase, issue.step_index, issue.field) == ("execution", 1, "if")


class TestAStepOutputIsReadOnlyWhenPublished:
    def test_a_typo_in_the_step_id_is_refused(self) -> None:
        [message] = _messages("${{ vars.execution.first_stauts.value == 'RECEIVED' }}")
        assert "execution.first_stauts" in message

    def test_a_field_the_step_does_not_return_is_refused(self) -> None:
        [message] = _messages("${{ vars.execution.first_status.status == 'RECEIVED' }}")
        assert "returns: value" in message

    def test_a_step_that_runs_later_is_refused(self) -> None:
        test = _test(execution=[_gated("${{ vars.execution.first_status.value }}"), _EXTRACT])
        assert len(_errors(test)) == 1

    def test_the_step_itself_is_refused(self) -> None:
        gated = _EXTRACT.model_copy(update={"if_condition": "vars.execution.first_status.value"})
        assert len(_errors(_test(execution=[gated]))) == 1

    def test_a_setup_step_is_readable_from_execution(self) -> None:
        test = _test(setup=[_EXTRACT], execution=[_gated("vars.setup.first_status.value")])
        assert _errors(test) == []

    def test_a_step_named_whole_is_refused(self) -> None:
        [message] = _messages("${{ vars.execution.first_status == 'x' }}")
        assert "names a step, not a value" in message

    def test_a_step_nested_in_a_flow_step_publishes_its_returns(self) -> None:
        retry = StepDefinition(
            id="retry",
            uses="flow/retry",
            with_={"steps": [_EXTRACT.model_dump(by_alias=True, exclude_none=True)]},
        )
        test = _test(execution=[retry, _gated("vars.execution.first_status.value == 'x'")])
        assert _errors(test) == []


class TestABareVariableMustExist:
    def test_an_undeclared_variable_is_refused(self) -> None:
        [message] = _messages("${{ vars.regoin == 'eu' }}")
        assert "names nothing this run holds" in message

    def test_a_manifest_variable_named_as_a_reference_is_refused_with_its_id(self) -> None:
        [message] = _messages("${{ vars.env.region == 'eu' }}")
        assert "'vars.region'" in message

    def test_without_a_manifest_a_bare_variable_is_not_guessed_at(self) -> None:
        test = _test(execution=[_gated("vars.anything == 'x'")])
        assert [i for i in TestValidator().validate(test).issues if i.level == "error"] == []


class TestAStepOutcomeIsReadByTheId:
    def test_an_unknown_step_is_refused(self) -> None:
        [message] = _messages("${{ steps.first.outcome == 'success' }}")
        assert "names no step before this one" in message

    def test_an_outcome_no_step_has_is_refused(self) -> None:
        [message] = _messages("${{ steps.first_status.outcome == 'passed' }}")
        assert "'success', 'failure' or 'skipped'" in message

    def test_a_setup_step_is_not_an_outcome_execution_can_read(self) -> None:
        test = _test(
            setup=[_EXTRACT], execution=[_gated("steps.first_status.outcome == 'success'")]
        )
        assert len(_errors(test)) == 1


class TestAnIfNothingReadsIsRefused:
    def test_teardown_ignores_if(self) -> None:
        [issue] = _errors(_test(teardown=[_gated("${{ always() }}")]))
        assert (issue.phase, issue.field) == ("teardown", "if")

    def test_a_nested_step_ignores_its_own_if(self) -> None:
        nested = {"uses": "util/log", "with": {"message": "m"}, "if": "${{ always() }}"}
        retry = StepDefinition(id="retry", uses="flow/retry", with_={"steps": [nested]})
        [issue] = _errors(_test(execution=[retry]))
        assert issue.field == "with.steps[0].if"
        assert "flow/if" in issue.message

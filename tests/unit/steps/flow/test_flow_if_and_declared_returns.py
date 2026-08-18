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

"""Tests for ``flow/if`` and for the declared-returns restriction (C06, C40)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from tractusx_testlab.models import HttpResponse, StepDefinition
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution.step_runner import store_step_outputs
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps._checks.extraction import declared_names, extract_path
from tractusx_testlab.steps.assertions import apply_operator
from tractusx_testlab.steps.flow.conditional import IfStep
from tractusx_testlab.steps.step_contract import StepOutput


def _definition(uses: str = "flow/if") -> StepDefinition:
    return StepDefinition(id="branch", uses=uses)


def _log(step_id: str) -> dict:
    """A nested step definition that always succeeds and records something."""
    return {"id": step_id, "uses": "util/log", "with": {"message": step_id}}


# ---------------------------------------------------------------------------
# C06 — flow/if
# ---------------------------------------------------------------------------


class TestIfStep:
    @pytest.mark.asyncio
    async def test_a_true_condition_runs_the_then_branch(self, mock_context: MagicMock) -> None:
        output = await IfStep().invoke(
            {
                "conditions": [{"input": "push", "operator": "equals", "value": "push"}],
                "then": [_log("in_then")],
            },
            mock_context,
            _definition(),
        )

        assert output.value["condition_result"] is True
        assert output.value["branch_taken"] == "then"
        assert len(output.value["outputs"]) == 1

    @pytest.mark.asyncio
    async def test_a_false_condition_runs_the_else_branch(self, mock_context: MagicMock) -> None:
        output = await IfStep().invoke(
            {
                "conditions": [{"input": "pull", "operator": "equals", "value": "push"}],
                "then": [_log("in_then")],
                "else": [_log("in_else")],
            },
            mock_context,
            _definition(),
        )

        assert output.value["condition_result"] is False
        assert output.value["branch_taken"] == "else"

    @pytest.mark.asyncio
    async def test_a_false_condition_with_no_else_does_nothing(
        self, mock_context: MagicMock
    ) -> None:
        """'none' is a result a script can assert on; silence is not."""
        output = await IfStep().invoke(
            {
                "conditions": [{"input": "pull", "operator": "equals", "value": "push"}],
                "then": [_log("in_then")],
            },
            mock_context,
            _definition(),
        )

        assert output.value["branch_taken"] == "none"
        assert output.value["outputs"] == []

    @pytest.mark.asyncio
    async def test_a_failing_nested_step_fails_the_branch(self, mock_context: MagicMock) -> None:
        with pytest.raises(RuntimeError, match="'then' branch"):
            await IfStep().invoke(
                {
                    "conditions": [{"input": "x", "operator": "not_null"}],
                    "then": [{"id": "x", "uses": "no/such/step"}],
                },
                mock_context,
                _definition(),
            )

    @pytest.mark.asyncio
    async def test_a_branch_with_no_steps_is_rejected(self, mock_context: MagicMock) -> None:
        """An 'if' whose 'then' does nothing is a script mistake, not a no-op."""
        with pytest.raises(ValueError, match="then"):
            await IfStep().invoke(
                {"conditions": [{"input": "x"}], "then": []}, mock_context, _definition()
            )

    @pytest.mark.asyncio
    async def test_all_means_every_condition_has_to_hold(self, mock_context: MagicMock) -> None:
        output = await IfStep().invoke(
            {
                "conditions": [
                    {"input": "push", "operator": "equals", "value": "push"},
                    {"input": None, "operator": "not_null"},
                ],
                "then": [_log("in_then")],
            },
            mock_context,
            _definition(),
        )
        assert output.value["condition_result"] is False

    @pytest.mark.asyncio
    async def test_any_means_one_is_enough(self, mock_context: MagicMock) -> None:
        output = await IfStep().invoke(
            {
                "match": "any",
                "conditions": [
                    {"input": "push", "operator": "equals", "value": "push"},
                    {"input": None, "operator": "not_null"},
                ],
                "then": [_log("in_then")],
            },
            mock_context,
            _definition(),
        )
        assert output.value["condition_result"] is True

    @pytest.mark.asyncio
    async def test_a_condition_reads_into_its_input_by_path(self, mock_context: MagicMock) -> None:
        output = await IfStep().invoke(
            {
                "conditions": [
                    {
                        "input": {"content": {"state": "RECEIVED"}},
                        "path": "content.state",
                        "operator": "equals",
                        "value": "RECEIVED",
                    }
                ],
                "then": [_log("in_then")],
            },
            mock_context,
            _definition(),
        )
        assert output.value["branch_taken"] == "then"

    def test_the_else_branch_is_spelled_else_in_a_script(self) -> None:
        """``else`` is a Python keyword; the script keyword is what matters."""
        params = IfStep.params_model.model_validate(
            {
                "conditions": [{"input": "x"}],
                "then": [_log("a")],
                "else": [_log("b")],
            }
        )
        assert len(params.otherwise) == 1

    def test_the_python_attribute_name_is_not_a_second_spelling(self) -> None:
        """``otherwise:`` in a script would be ``else:`` under another name."""
        with pytest.raises(ValidationError, match="otherwise"):
            IfStep.params_model.model_validate(
                {
                    "conditions": [{"input": "x"}],
                    "then": [_log("a")],
                    "otherwise": [_log("b")],
                }
            )


# ---------------------------------------------------------------------------
# C40 — a returns: name resolves only when the step declared it
# ---------------------------------------------------------------------------


class TestDeclaredNames:
    def test_a_steps_declared_output_fields_are_readable(self) -> None:
        names = declared_names(StepRegistry.get("connector/consumer/negotiate", ""))
        assert {"negotiation_id", "agreement_id", "state"} <= names

    def test_what_a_step_publishes_is_readable_too(self) -> None:
        names = declared_names(StepRegistry.get("connector/consumer/initiate_transfer", ""))
        assert "transfer_id" in names

    def test_the_universal_slots_stay_readable(self) -> None:
        """Every step reports a request and a response; scripts assert on them."""
        names = declared_names(StepRegistry.get("http/http_request", ""))
        assert {"status_code", "response_body", "response_headers"} <= names


class TestReturnsRestriction:
    def test_an_undeclared_name_does_not_resolve_from_the_response(self) -> None:
        output = StepOutput(
            value={"negotiation_id": "neg-1"},
            response=HttpResponse(status_code=200, body={"secretInternalKey": "leaked"}),
        )
        assert extract_path(output, "secretInternalKey") == "leaked"
        assert extract_path(output, "secretInternalKey", frozenset({"negotiation_id"})) is None

    def test_a_declared_name_still_resolves(self) -> None:
        output = StepOutput(value={"negotiation_id": "neg-1"})
        assert extract_path(output, "negotiation_id", frozenset({"negotiation_id"})) == "neg-1"

    def test_returns_reads_only_what_the_step_declared(self, mock_context: MagicMock) -> None:
        """A `returns:` name the step never declared must not be invented."""
        step_def = StepDefinition(
            id="neg",
            uses="connector/consumer/negotiate",
            returns={
                "negotiation_id": {"type": "string"},
                "contractAgreementId": {"type": "string"},
            },
        )
        result = StepResult(
            step_name="neg",
            step_type="connector/consumer/negotiate",
            output={"negotiation_id": "neg-1"},
            response=HttpResponse(status_code=200, body={"contractAgreementId": "agr-1"}),
        )

        store_step_outputs(step_def, result, mock_context)

        assert mock_context.variables["negotiation_id"] == "neg-1"
        assert mock_context.variables["contractAgreementId"] is None


# ---------------------------------------------------------------------------
# The operators a condition and an assertion share
# ---------------------------------------------------------------------------


class TestSharedOperators:
    """``flow/if`` and ``validate:`` compare through one table, so both grew here."""

    @pytest.mark.parametrize(
        ("operator", "actual", "expected", "holds"),
        [
            ("one_of", "STARTED", ["STARTED", "COMPLETED"], True),
            ("one_of", "TERMINATED", ["STARTED", "COMPLETED"], False),
            ("none_of", "TERMINATED", ["STARTED"], True),
            ("gt", 5, 3, True),
            ("gte", 3, 3, True),
            ("lt", 3, 5, True),
            ("lte", 5, 3, False),
            ("has_key", {"a": 1}, "a", True),
            ("not_has_key", {"a": 1}, "b", True),
            ("length_equals", [1, 2], 2, True),
            ("length_gt", [1, 2], 1, True),
            ("length_lt", [1, 2], 5, True),
            ("is_null", None, None, True),
        ],
    )
    def test_the_ide_operator_set_is_covered(
        self, operator: str, actual: object, expected: object, holds: bool
    ) -> None:
        assert apply_operator(operator, actual, expected)[0] is holds

    def test_a_value_with_no_length_does_not_compare(self) -> None:
        """A missing value must read as "does not hold", never as a crash."""
        assert apply_operator("length_gt", None, 1)[0] is False

    def test_a_value_that_is_not_a_number_does_not_compare(self) -> None:
        assert apply_operator("gt", "abc", 1)[0] is False

    def test_an_unknown_operator_says_so(self) -> None:
        holds, message = apply_operator("sideways", 1, 1)
        assert holds is False
        assert "Unknown operator" in message

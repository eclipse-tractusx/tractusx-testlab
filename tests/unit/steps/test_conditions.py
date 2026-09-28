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

"""How the player evaluates a step's ``if:`` — the grammar the compiler holds tests to."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.steps._condition_parsing import Condition, parse_condition
from tractusx_testlab.steps.conditions import ConditionEvaluator


def _context(**variables: object) -> MagicMock:
    context = MagicMock()
    context.get_variable.side_effect = lambda name, default=None: variables.get(name, default)
    return context


def _result(step_id: str, status: StepStatus) -> StepResult:
    return StepResult(step_name=f"t[{step_id}]:util/log", step_type="util/log", status=status)


class TestParsing:
    @pytest.mark.parametrize(
        ("condition", "parsed"),
        [
            ("", Condition("status", "success")),
            ("${{ always() }}", Condition("status", "always")),
            (
                "${{ steps.fetch.outcome != 'failure' }}",
                Condition("outcome", "fetch", "!=", "failure"),
            ),
            (
                "${{ vars.execution.first.value == 'RECEIVED' }}",
                Condition("compare", "execution.first.value", "==", "RECEIVED"),
            ),
            ("vars.flag", Condition("truthy", "flag")),
            ("${flag} == on", Condition("compare", "flag", "==", "on", legacy=True)),
        ],
    )
    def test_each_form_parses_to_what_it_reads(self, condition: str, parsed: Condition) -> None:
        assert parse_condition(condition) == parsed

    def test_anything_else_is_not_the_grammar(self) -> None:
        assert parse_condition("${{ vars.a == 'x' and vars.b == 'y' }}") is None


class TestEvaluation:
    def test_a_step_output_is_compared_under_its_phase_and_id(self) -> None:
        condition = "${{ vars.execution.first.value == 'RECEIVED' }}"
        received = _context(**{"execution.first.value": "RECEIVED"})
        accepted = _context(**{"execution.first.value": "ACCEPTED"})
        assert ConditionEvaluator.should_run(condition, [], received) is True
        assert ConditionEvaluator.should_run(condition, [], accepted) is False

    def test_an_outcome_is_read_from_the_step_with_that_exact_id(self) -> None:
        # `fetch_again` ran later and failed; a substring match used to read it
        # as the outcome of `fetch`.
        results = [_result("fetch", StepStatus.PASSED), _result("fetch_again", StepStatus.FAILED)]
        condition = "${{ steps.fetch.outcome == 'success' }}"
        assert ConditionEvaluator.should_run(condition, results, _context()) is True

    def test_a_setup_step_is_found_by_its_id(self) -> None:
        result = StepResult(
            step_name="t[setup:seed]:util/log", step_type="util/log", status=StepStatus.FAILED
        )
        condition = "steps.seed.outcome == 'failure'"
        assert ConditionEvaluator.should_run(condition, [result], _context()) is True

    def test_an_unrecognised_expression_runs_the_step_and_says_so(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            assert ConditionEvaluator.should_run("${{ nonsense }}", [], _context()) is True
        assert "nonsense" in caplog.text

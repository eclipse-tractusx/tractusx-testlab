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

"""A ``validate:`` entry's ``severity`` is HARD or SOFT, in any case, and nothing else.

The compiler used to accept any word, so ``severity: warning`` compiled cleanly
and the run then stopped on it. Nested steps run their own ``validate:``
entries, so theirs are held to the same rule.
"""

from __future__ import annotations

import pytest

from tractusx_testlab.compiler.validation.issues import ValidationIssue
from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.models import StepDefinition, TestDefinition


def _check(severity: object) -> dict:
    return {
        "uses": "validate/assert",
        "with": {"input": "value", "operator": "not_null", "severity": severity},
    }


def _mint(*checks: dict) -> dict:
    return {"id": "mint", "uses": "util/generate_uuid", "validate": list(checks)}


def _severity_errors(step: StepDefinition) -> list[ValidationIssue]:
    test = TestDefinition(
        syntax="v1-alpha",
        kind="test",
        id="t",
        namespace="n",
        metadata={"name": "t"},
        execution=[step],
    )
    result = TestValidator().validate(test)
    return [
        issue
        for issue in result.issues
        if issue.level == "error" and (issue.field or "").endswith("severity")
    ]


class TestSeverityValues:
    @pytest.mark.parametrize("severity", ["HARD", "SOFT", "hard", "soft", "Soft"])
    def test_hard_and_soft_compile_in_any_case(self, severity: str) -> None:
        assert _severity_errors(StepDefinition(**_mint(_check(severity)))) == []

    @pytest.mark.parametrize("severity", ["warning", "WARNING", "error", "", 1, None])
    def test_any_other_value_is_refused(self, severity: object) -> None:
        errors = _severity_errors(StepDefinition(**_mint(_check(severity))))
        assert len(errors) == 1

    def test_the_finding_names_the_value_and_the_severities(self) -> None:
        [error] = _severity_errors(StepDefinition(**_mint(_check("warning"))))
        assert "'warning'" in error.message
        assert "'HARD'" in error.message and "'SOFT'" in error.message

    def test_the_finding_is_located_at_the_validate_entry(self) -> None:
        step = StepDefinition(**_mint(_check("soft"), _check("warning")))
        [error] = _severity_errors(step)
        assert (error.phase, error.step_index) == ("execution", 0)
        assert error.field == "validate[1].with.severity"

    def test_a_reference_is_left_to_the_run(self) -> None:
        step = StepDefinition(**_mint(_check("${{ env.severity }}")))
        assert _severity_errors(step) == []


class TestNestedSeverities:
    def test_a_retried_steps_severity_is_checked_at_its_path(self) -> None:
        step = StepDefinition(
            id="attempt", uses="flow/retry", with_={"steps": [_mint(_check("warning"))]}
        )
        [error] = _severity_errors(step)
        assert error.field == "with.steps[0].validate[0].with.severity"

    def test_a_step_two_deep_in_a_labs_loop_is_checked(self) -> None:
        branch = {
            "id": "branch",
            "uses": "flow/if",
            "with": {
                "conditions": [{"input": "go", "operator": "not_null"}],
                "then": [_mint(_check("soft"), _check("nope"))],
            },
        }
        step = StepDefinition(
            id="loop", uses="labs/flow/for_each", with_={"items": [1], "steps": [branch]}
        )
        [error] = _severity_errors(step)
        assert error.field == "with.steps[0].with.then[0].validate[1].with.severity"

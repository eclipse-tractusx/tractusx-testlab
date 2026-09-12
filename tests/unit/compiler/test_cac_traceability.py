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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""``cac:`` names the conformity assessment criteria a step or a check verifies.

Traceability only — it never changes a verdict — but it is only worth writing if
it is well-formed, names a standard the TCK certifies against, and reaches the
trace a report is drawn up from. Each of those is pinned here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.models import TckDefinition
from tractusx_testlab.models.authoring.definitions import Assertion, StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.results import AssertionResult, StepResult
from tractusx_testlab.player.execution._trace_events import step_data
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.steps.util.log import LogStep
from tractusx_testlab.syntax import diagnostics


def _step(**extra) -> dict:
    return {"id": "act", "name": "Act", "uses": "util/log", "with": {"message": "hi"}, **extra}


def _cac_errors(tmp_path: Path, step: dict, standards: list[dict]) -> list[str]:
    manifest = {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "cac-tck",
        "metadata": {"name": "CAC", "standards": standards},
        "tests": [{"id": "t.yaml"}],
    }
    test = {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "t",
        "namespace": "cac-tck",
        "metadata": {"name": "t"},
        "execution": [step],
    }
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.yaml").write_text(yaml.dump(test), encoding="utf-8")
    result = TestValidator().validate_tck(TckDefinition.model_validate(manifest), tmp_path)
    return [issue.message for issue in result.issues if "cac" in issue.message]


CX_0135 = [{"id": "CX-0135", "version": "v3.1.0"}]


class TestTheReferenceIsWellFormed:
    def test_standard_version_and_cac_are_accepted(self) -> None:
        step = StepDefinition.model_validate(_step(cac=["CX-0135:v3.1.0:CAC-014"]))
        assert step.cac == ["CX-0135:v3.1.0:CAC-014"]

    @pytest.mark.parametrize("reference", ["CAC-014", "CX-0135:CAC-014", "CX-0135::CAC-014"])
    def test_a_reference_missing_a_segment_is_refused(self, reference: str) -> None:
        with pytest.raises(ValidationError):
            StepDefinition.model_validate(_step(cac=[reference]))

    def test_the_refusal_is_written_for_the_author(self) -> None:
        with pytest.raises(ValidationError) as caught:
            Assertion.model_validate({"uses": "validate/assert", "cac": ["CAC-014"]})
        message = diagnostics.render(caught.value, model=Assertion)
        assert "<standard-id>:<standard-version>:<cac-id>" in message
        assert "pattern" not in message


class TestTheStandardIsCertified:
    def test_a_listed_standard_is_accepted(self, tmp_path) -> None:
        assert _cac_errors(tmp_path, _step(cac=["CX-0135:v3.1.0:CAC-014"]), CX_0135) == []

    def test_an_unlisted_standard_is_refused(self, tmp_path) -> None:
        (error,) = _cac_errors(tmp_path, _step(cac=["CX-0018:v4.2.0:CAC-001"]), CX_0135)
        assert "CX-0018 v4.2.0" in error
        assert "CX-0135:v3.1.0" in error

    def test_another_version_of_a_listed_standard_is_refused(self, tmp_path) -> None:
        """The usual cause: the manifest was bumped and the tests were not."""
        (error,) = _cac_errors(tmp_path, _step(cac=["CX-0135:v3.0.0:CAC-014"]), CX_0135)
        assert "v3.0.0" in error

    def test_a_check_is_held_to_the_same_manifest(self, tmp_path) -> None:
        check = {"uses": "validate/assert", "cac": ["CX-9999:v1.0.0:CAC-1"], "with": {}}
        (error,) = _cac_errors(tmp_path, _step(validate=[check]), CX_0135)
        assert "CX-9999" in error

    def test_a_step_inside_a_flow_branch_is_held_to_it_too(self, tmp_path) -> None:
        branch = {
            "id": "flow",
            "name": "Branch",
            "uses": "flow/if",
            "with": {
                "conditions": [{"input": 1, "operator": "equals", "value": 1}],
                "then": [_step(cac=["CX-9999:v1.0.0:CAC-1"])],
            },
        }
        (error,) = _cac_errors(tmp_path, branch, CX_0135)
        assert "CX-9999" in error


class TestTheTraceCarriesIt:
    def _result(self, check_cac: list[str] | None) -> StepResult:
        check = Assertion(uses="validate/assert", cac=check_cac, with_={"input": "value"})
        return StepResult(
            step_name="s",
            step_type="util/log",
            status=StepStatus.PASSED,
            cac=["CX-0135:v3.1.0:CAC-014"],
            assertions=[AssertionResult(assertion=check, passed=True)],
        )

    def test_the_step_event_names_the_step_cac(self) -> None:
        assert step_data(self._result(None))["cac"] == ["CX-0135:v3.1.0:CAC-014"]

    def test_a_check_without_its_own_reports_under_the_step(self) -> None:
        (validation,) = step_data(self._result(None))["validations"]
        assert validation["cac"] == ["CX-0135:v3.1.0:CAC-014"]

    def test_a_check_with_its_own_overrides_the_step(self) -> None:
        (validation,) = step_data(self._result(["CX-0135:v3.1.0:CAC-015"]))["validations"]
        assert validation["cac"] == ["CX-0135:v3.1.0:CAC-015"]

    def test_a_step_without_one_publishes_no_key(self) -> None:
        data = step_data(StepResult(step_name="s", status=StepStatus.PASSED))
        assert "cac" not in data


class TestTheRunnerCarriesIt:
    async def test_the_result_names_the_cac_its_definition_declared(self, mock_context) -> None:
        definition = StepDefinition.model_validate(_step(cac=["CX-0135:v3.1.0:CAC-014"]))
        result = await run_step(LogStep, definition, "act", mock_context)
        assert result.cac == ["CX-0135:v3.1.0:CAC-014"]

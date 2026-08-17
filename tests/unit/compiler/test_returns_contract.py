################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## It was reviewed and tested by a human committer.

"""A ``returns:`` name must be something the step actually publishes.

Until this check existed, a name the step never declared compiled cleanly and
resolved to nothing at run time — the variable read as empty several steps
later, far from the typo that caused it.
"""

from __future__ import annotations

from tractusx_testlab.compiler.validation.validator import ScriptValidator
from tractusx_testlab.models import ScriptDefinition, StepDefinition


def _errors_for(uses: str, returns: dict) -> list[str]:
    script = ScriptDefinition(
        syntax="v1-alpha",
        kind="test",
        id="t",
        name="t",
        namespace="n",
        metadata={"name": "t"},
        execution=[StepDefinition(id="s1", uses=uses, returns=returns)],
    )
    result = ScriptValidator().validate(script)
    return [issue.message for issue in result.issues if issue.level == "error"]


class TestReturnsAreChecked:
    def test_a_declared_output_is_accepted(self) -> None:
        assert _errors_for("util/generate_uuid", {"value": {"type": "string"}}) == []

    def test_a_name_the_step_never_publishes_is_rejected(self) -> None:
        errors = _errors_for("util/generate_uuid", {"not_a_real_output": {"type": "string"}})
        assert len(errors) == 1
        assert "not_a_real_output" in errors[0]

    def test_the_error_names_what_the_step_does_publish(self) -> None:
        errors = _errors_for("util/generate_uuid", {"nope": {"type": "string"}})
        assert "value" in errors[0]

    def test_universal_returns_are_readable_on_any_step(self) -> None:
        # Every step carries the response envelope whatever else it declares.
        assert _errors_for("util/generate_uuid", {"status_code": {"type": "integer"}}) == []

    def test_a_path_into_a_declared_output_is_accepted(self) -> None:
        assert _errors_for(
            "connector/consumer/initiate_transfer",
            {"data_address.endpoint": {"type": "string"}},
        ) == []

    def test_an_unknown_step_is_not_second_guessed(self) -> None:
        # The unknown-step error is the finding; guessing at its outputs is not.
        errors = _errors_for("no/such/step", {"whatever": {"type": "string"}})
        assert all("returns" not in message for message in errors)


class TestDeletedOutputNamesAreCaught:
    """The contract changes this check was added alongside stay enforced."""

    def test_the_removed_generate_uuid_alias_is_rejected(self) -> None:
        errors = _errors_for("util/generate_uuid", {"generated_id": {"type": "string"}})
        assert len(errors) == 1

    def test_delete_shell_descriptor_now_publishes_a_status_code(self) -> None:
        assert _errors_for(
            "digital-twin/provider/delete_shell_descriptor",
            {"status_code": {"type": "integer"}},
        ) == []

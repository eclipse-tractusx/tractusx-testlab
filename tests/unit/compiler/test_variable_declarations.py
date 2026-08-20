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

"""What a manifest may declare under ``env.variables``.

The block used to be unchecked, so a verb that does not exist, a ``returns:``
naming a key nothing publishes, and a variable nothing would seed all compiled
and failed at the first step that read them.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.compiler.validation._variable_declarations import (
    declared_variable_ids,
    validate_variable_declarations,
    validate_variable_references,
)


def _env(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"variables": list(entries)}


def _policy(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "usage_policy",
        "uses": "config/connector/policy",
        "with": {"value": {"permissions": [{"action": "use"}]}},
        "returns": {"value": {"type": "object", "class": "Policy"}},
    }
    entry.update(overrides)
    return entry


def _string(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": "valid_bpn",
        "uses": "variable/type/string",
        "with": {"source": "input", "scope": "engine"},
        "returns": {"value": {"type": "string"}},
    }
    entry.update(overrides)
    return entry


class TestTheVerbMustExist:
    def test_a_well_formed_block_passes(self) -> None:
        assert validate_variable_declarations(_env(_policy(), _string())) == []

    def test_an_unknown_verb_is_rejected_with_the_ones_that_exist(self) -> None:
        errors = validate_variable_declarations(_env(_policy(uses="config/connector/policies")))

        assert len(errors) == 1
        assert "config/connector/policies" in errors[0]
        assert "config/connector/policy" in errors[0]

    def test_a_generated_variable_says_what_to_write_instead(self) -> None:
        """The grammar parses ``generate/*``; nothing in the engine seeds one."""
        errors = validate_variable_declarations(
            _env({"id": "asset_id", "uses": "generate/uuid_v4", "with": {}})
        )

        assert len(errors) == 1
        assert "util/generate_uuid" in errors[0]

    def test_a_variable_without_a_verb_is_rejected(self) -> None:
        errors = validate_variable_declarations(_env({"id": "orphan", "with": {"value": "x"}}))

        assert len(errors) == 1
        assert "no 'uses'" in errors[0]


class TestEveryVariablePublishesValue:
    def test_the_old_artifact_key_is_rejected_and_names_its_replacement(self) -> None:
        errors = validate_variable_declarations(
            _env(_policy(returns={"policy": {"type": "object", "class": "Policy"}}))
        )

        assert len(errors) == 1
        assert "publishes under 'policy'" in errors[0]
        assert "returns: { value: { type: object, class: Policy } }" in errors[0]
        assert "${{ env.usage_policy }}" in errors[0]

    def test_a_missing_returns_block_is_rejected(self) -> None:
        entry = _policy()
        del entry["returns"]

        errors = validate_variable_declarations(_env(entry))

        assert len(errors) == 1
        assert "no 'returns'" in errors[0]


class TestTheTypeIsBoundToTheVerb:
    def test_a_type_the_verb_does_not_publish_is_rejected(self) -> None:
        errors = validate_variable_declarations(
            _env(_policy(returns={"value": {"type": "string", "class": "Policy"}}))
        )

        assert len(errors) == 1
        assert "publishes a object" in errors[0]
        assert "type: string" in errors[0]

    def test_a_missing_class_on_a_domain_object_is_rejected(self) -> None:
        errors = validate_variable_declarations(
            _env(_policy(returns={"value": {"type": "object"}}))
        )

        assert len(errors) == 1
        assert "publishes a Policy" in errors[0]

    def test_a_class_on_a_plain_value_is_rejected(self) -> None:
        errors = validate_variable_declarations(
            _env(_string(returns={"value": {"type": "string", "class": "Policy"}}))
        )

        assert len(errors) == 1
        assert "plain string" in errors[0]

    def test_a_format_note_is_allowed_beside_the_type(self) -> None:
        """``format`` describes the shape the operator must supply; no verb knows it."""
        entry = _string(returns={"value": {"type": "string", "format": "bpn"}})

        assert validate_variable_declarations(_env(entry)) == []

    def test_an_unknown_key_under_value_is_rejected(self) -> None:
        errors = validate_variable_declarations(
            _env(_string(returns={"value": {"type": "string", "placeholder": "BPNL…"}}))
        )

        assert len(errors) == 1
        assert "placeholder" in errors[0]


class TestSomethingMustSeedIt:
    def test_a_variable_with_no_value_and_no_operator_is_rejected(self) -> None:
        errors = validate_variable_declarations(_env(_policy(**{"with": {}})))

        assert len(errors) == 1
        assert "Nothing would seed it" in errors[0]

    def test_an_unrecognized_source_is_rejected(self) -> None:
        errors = validate_variable_declarations(_env(_string(**{"with": {"source": "runtime"}})))

        assert len(errors) == 1
        assert "unrecognized source 'runtime'" in errors[0]

    def test_a_duplicate_id_is_rejected(self) -> None:
        errors = validate_variable_declarations(_env(_string(), _string()))

        assert len(errors) == 1
        assert "declared twice" in errors[0]

    def test_every_entry_is_reported_not_just_the_first(self) -> None:
        errors = validate_variable_declarations(
            _env(_policy(uses="config/connector/nope"), _string(returns={"value": {}}))
        )

        assert len(errors) == 2


class TestTheValueMustReadAsTheDeclaredType:
    """A structure written as text is read at compile time, not at run start."""

    def test_a_json_block_that_does_not_parse_is_rejected(self) -> None:
        errors = validate_variable_declarations(
            _env(_policy(**{"with": {"value": '{"permission": [{"action": "use"} {}]}'}}))
        )

        assert len(errors) == 1
        assert "usage_policy" in errors[0]
        assert "type: object" in errors[0]

    def test_the_parser_complaint_is_one_line_naming_the_place(self) -> None:
        """A compile report lists one finding per line; four lines of parser lose three."""
        errors = validate_variable_declarations(
            _env(_policy(**{"with": {"value": '{"permission": [{} {}]}'}}))
        )

        assert "\n" not in errors[0]
        assert "line 1, column 20 of the value" in errors[0]

    def test_text_that_parses_to_a_scalar_is_rejected(self) -> None:
        errors = validate_variable_declarations(
            _env(_policy(**{"with": {"value": "the usual usage policy"}}))
        )

        assert "reads as str" in errors[0]

    def test_a_json_block_that_parses_is_accepted(self) -> None:
        value = '{"permission": [{"action": "use"}], "prohibition": [], "obligation": []}'

        assert validate_variable_declarations(_env(_policy(**{"with": {"value": value}}))) == []

    def test_a_string_variable_holding_json_text_is_left_alone(self) -> None:
        """Only a declared structure is parsed — a filter the SUT takes as text is text."""
        entry = _string(**{"with": {"value": '[{"name": "digitalTwinType"}]'}})

        assert validate_variable_declarations(_env(entry)) == []


class TestReferencesIntoAVariable:
    def test_a_reference_to_the_old_artifact_key_is_rejected(self) -> None:
        test_data = {
            "execution": [
                {
                    "id": "pull",
                    "uses": "connector/consumer/pull_data_filtered",
                    "with": {"expected_policies": "${{ env.usage_policy.policy }}"},
                }
            ]
        }

        errors = validate_variable_references(
            test_data, declared_variable_ids(_env(_policy())), "tests/pull.yaml"
        )

        assert len(errors) == 1
        assert "reaches into variable" in errors[0]
        assert "${{ env.usage_policy }}" in errors[0]

    def test_the_publishing_key_is_rejected_too(self) -> None:
        """``.value`` is the key the artifact key became — still a path, not a name."""
        test_data = {
            "execution": [
                {
                    "id": "pull",
                    "uses": "connector/consumer/pull_data_filtered",
                    "with": {"expected_policies": "${{ env.usage_policy.value }}"},
                }
            ]
        }

        errors = validate_variable_references(
            test_data, declared_variable_ids(_env(_policy())), "tests/pull.yaml"
        )

        assert len(errors) == 1
        assert "${{ env.usage_policy }}" in errors[0]

    def test_the_whole_variable_passes(self) -> None:
        test_data = {
            "execution": [
                {
                    "id": "pull",
                    "uses": "connector/consumer/pull_data_filtered",
                    "with": {"expected_policies": "${{ env.usage_policy }}"},
                }
            ]
        }

        ids = declared_variable_ids(_env(_policy()))

        assert validate_variable_references(test_data, ids, "tests/pull.yaml") == []

    def test_testdata_and_step_outputs_are_left_alone(self) -> None:
        """Only a declared variable's id is a variable; the other roots are not."""
        test_data = {
            "execution": [
                {
                    "id": "check",
                    "uses": "validate/schema",
                    "with": {
                        "schema": "${{ env.schemas.cert }}",
                        "input": "${{ execution.pull.dataplane_url }}",
                    },
                }
            ]
        }

        ids = declared_variable_ids(_env(_policy()))

        assert validate_variable_references(test_data, ids, "tests/check.yaml") == []

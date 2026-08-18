###############################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Unit tests for VariableScope: parsing, model, compiler validation."""

from __future__ import annotations

import pytest

from tests.paths import CCM_RAW_DIR
from tractusx_testlab.compiler.validation._rules import (
    _validate_scoped_sides_are_declared,
    _validate_variable_scopes,
)
from tractusx_testlab.models.primitives.enums import VariableScope, VariableSource
from tractusx_testlab.scripting._variable_form import parse_variables_block


class TestVariableScopeEnum:
    def test_engine_value_is_engine(self) -> None:
        assert VariableScope.ENGINE.value == "engine"

    def test_sut_value_is_sut(self) -> None:
        assert VariableScope.SUT.value == "sut"

    def test_coerce_from_string_engine(self) -> None:
        assert VariableScope("engine") is VariableScope.ENGINE

    def test_coerce_from_string_sut(self) -> None:
        assert VariableScope("sut") is VariableScope.SUT

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValueError):
            VariableScope("shared")


class TestVariableScopeParsing:
    def test_verb_variable_with_scope_engine_is_parsed(self) -> None:
        raw = [
            {
                "id": "mgmt_url",
                "uses": "variable/type/string",
                "with": {"source": "input", "scope": "engine"},
                "returns": {"value": {"type": "string"}},
            }
        ]

        result = parse_variables_block(raw)

        assert result["mgmt_url"].scope is VariableScope.ENGINE

    def test_verb_variable_with_scope_sut_is_parsed(self) -> None:
        raw = [
            {
                "id": "provider_bpn",
                "uses": "variable/type/string",
                "with": {"source": "input", "scope": "sut"},
                "returns": {"value": {"type": "string"}},
            }
        ]

        result = parse_variables_block(raw)

        assert result["provider_bpn"].scope is VariableScope.SUT

    def test_verb_variable_without_scope_has_none_scope(self) -> None:
        raw = [
            {
                "id": "timeout",
                "uses": "variable/type/integer",
                "with": {"value": 300},
                "returns": {"value": {"type": "integer"}},
            }
        ]

        result = parse_variables_block(raw)

        assert result["timeout"].scope is None

    def test_scope_is_not_set_on_value_source_variable(self) -> None:
        raw = [
            {
                "id": "cert_type",
                "uses": "variable/type/string",
                "with": {"value": "iso9001"},
            }
        ]

        result = parse_variables_block(raw)

        assert result["cert_type"].source is VariableSource.VALUE
        assert result["cert_type"].scope is None


class TestValidateVariableScopes:
    def test_input_variable_missing_scope_produces_error(self) -> None:
        env = {
            "variables": [
                {
                    "id": "mgmt_url",
                    "uses": "variable/type/string",
                    "with": {"source": "input"},
                }
            ]
        }

        errors = _validate_variable_scopes(env)

        assert len(errors) == 1
        assert "mgmt_url" in errors[0]
        assert "scope" in errors[0]

    def test_input_variable_with_valid_scope_produces_no_error(self) -> None:
        env = {
            "variables": [
                {
                    "id": "mgmt_url",
                    "uses": "variable/type/string",
                    "with": {"source": "input", "scope": "engine"},
                }
            ]
        }

        errors = _validate_variable_scopes(env)

        assert errors == []

    def test_input_variable_with_invalid_scope_produces_error(self) -> None:
        env = {
            "variables": [
                {
                    "id": "mgmt_url",
                    "uses": "variable/type/string",
                    "with": {"source": "input", "scope": "shared"},
                }
            ]
        }

        errors = _validate_variable_scopes(env)

        assert len(errors) == 1
        assert "shared" in errors[0]
        assert "mgmt_url" in errors[0]

    def test_value_source_variable_without_scope_produces_no_error(self) -> None:
        env = {
            "variables": [
                {
                    "id": "cert_type",
                    "uses": "variable/type/string",
                    "with": {"value": "iso9001"},
                }
            ]
        }

        errors = _validate_variable_scopes(env)

        assert errors == []

    def test_multiple_missing_scopes_all_reported(self) -> None:
        env = {
            "variables": [
                {
                    "id": "var_a",
                    "uses": "variable/type/string",
                    "with": {"source": "input"},
                },
                {
                    "id": "var_b",
                    "uses": "variable/type/string",
                    "with": {"source": "input"},
                },
            ]
        }

        errors = _validate_variable_scopes(env)

        assert len(errors) == 2
        assert any("var_a" in e for e in errors)
        assert any("var_b" in e for e in errors)

    def test_empty_env_produces_no_error(self) -> None:
        assert _validate_variable_scopes({}) == []

    def test_env_with_no_variables_key_produces_no_error(self) -> None:
        assert _validate_variable_scopes({"schemas": []}) == []


class TestCcmVariableScopes:
    def _load_ccm_tck(self) -> object:
        from tractusx_testlab.scripting.parser import YamlParser
        from tractusx_testlab.scripting.script import Tck

        tck_def = YamlParser.parse_tck(CCM_RAW_DIR / "index.yaml")
        return Tck(tck_def)

    def test_a_variable_declared_sut_is_scoped_to_the_sut(self) -> None:
        """The example's own variables, read from it — names drift, the rule does not."""
        variables = self._load_ccm_tck().all_variables()

        sut_scoped = [name for name, var in variables.items() if var.scope is VariableScope.SUT]

        assert sut_scoped, "the CCM example declares no sut-scoped variable to check"
        for name in sut_scoped:
            assert variables[name].scope is VariableScope.SUT

    def test_every_declared_scope_round_trips_from_the_example(self) -> None:
        """What the YAML says a variable's scope is, is what the model reports."""
        import yaml

        raw = yaml.safe_load((CCM_RAW_DIR / "index.yaml").read_text(encoding="utf-8"))
        declared = {
            entry["id"]: (entry.get("with") or {}).get("scope")
            for entry in (raw.get("env") or {}).get("variables") or []
        }
        variables = self._load_ccm_tck().all_variables()

        assert declared, "the CCM example declares no env variables to check"
        for name, scope in declared.items():
            expected = VariableScope(scope) if scope else None
            assert variables[name].scope is expected, f"{name} lost its declared scope"


class TestScopedSidesAreDeclared:
    """A variable may only be asked of a side the TCK actually requires."""

    @staticmethod
    def _env(scope: str) -> dict:
        return {
            "variables": [
                {
                    "id": "sut_counter_party_id",
                    "uses": "variable/type/string",
                    "with": {"source": "input", "scope": scope},
                    "returns": {"value": {"type": "string"}},
                }
            ]
        }

    @staticmethod
    def _infrastructure(side: str, required: bool = True) -> dict:
        return {side: {"connector": {"required": required}}}

    def test_scope_matching_a_required_side_is_accepted(self) -> None:
        errors = _validate_scoped_sides_are_declared(
            self._env("sut"), self._infrastructure("sut")
        )

        assert errors == []

    def test_scope_without_any_infrastructure_block_is_rejected(self) -> None:
        errors = _validate_scoped_sides_are_declared(self._env("sut"), None)

        assert len(errors) == 1
        assert "requires no sut capability" in errors[0]

    def test_scope_naming_the_other_side_is_rejected(self) -> None:
        errors = _validate_scoped_sides_are_declared(
            self._env("engine"), self._infrastructure("sut")
        )

        assert len(errors) == 1
        assert "scoped to 'engine'" in errors[0]

    def test_a_capability_that_is_not_required_does_not_declare_the_side(self) -> None:
        """`required: false` describes what the run does NOT need — nobody to ask."""
        errors = _validate_scoped_sides_are_declared(
            self._env("sut"), self._infrastructure("sut", required=False)
        )

        assert len(errors) == 1

    def test_a_variable_carrying_its_own_value_needs_no_side(self) -> None:
        env = {
            "variables": [
                {
                    "id": "timeout",
                    "uses": "variable/type/integer",
                    "with": {"value": 300},
                    "returns": {"value": {"type": "integer"}},
                }
            ]
        }

        assert _validate_scoped_sides_are_declared(env, None) == []

    def test_the_error_names_the_variable_and_the_fix(self) -> None:
        [error] = _validate_scoped_sides_are_declared(self._env("sut"), {})

        assert "sut_counter_party_id" in error
        assert "infrastructure.sut.connector.required: true" in error

    def test_the_shipped_example_passes(self) -> None:
        """The CCM example declares the SUT connector its variables are asked of."""
        import yaml

        raw = yaml.safe_load((CCM_RAW_DIR / "index.yaml").read_text(encoding="utf-8"))

        errors = _validate_scoped_sides_are_declared(
            raw.get("env") or {}, raw.get("infrastructure")
        )

        assert errors == []

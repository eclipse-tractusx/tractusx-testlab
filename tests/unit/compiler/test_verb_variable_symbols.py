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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Tests for verb-form env.variables symbol generation (ADR-0018 unified variables)."""

from __future__ import annotations

from tractusx_testlab.compiler.ir._symbols import build_global_symbols


def _policy_variable() -> dict:
    """Return a verb-form `config/connector/policy` env variable entry."""
    return {
        "id": "ccm_usage_policy",
        "uses": "config/connector/policy",
        "name": "Required CCMAPI Usage Policy",
        "with": {"value": {"permissions": [{"action": "use"}]}},
        "returns": {"policy": {"type": "object", "class": "Policy"}},
    }


class TestVerbVariableSymbols:
    """build_global_symbols must register verb-form (list) env variables."""

    def test_list_form_variables_do_not_crash(self) -> None:
        env = {"variables": [{"id": "provider_url", "uses": "variable/type/string",
                              "with": {"source": "input"},
                              "returns": {"value": {"type": "string"}}}]}

        symbols = build_global_symbols(env)

        assert "env.provider_url" in symbols

    def test_simple_variable_uses_declared_return_type(self) -> None:
        env = {"variables": [{"id": "timeout", "uses": "variable/type/integer",
                              "with": {"value": 300},
                              "returns": {"value": {"type": "integer"}}}]}

        symbols = build_global_symbols(env)

        assert symbols["env.timeout"]["type"] == "integer"

    def test_simple_variable_value_return_is_not_a_subfield_symbol(self) -> None:
        env = {"variables": [{"id": "name", "uses": "variable/type/string",
                              "with": {"value": "x"},
                              "returns": {"value": {"type": "string"}}}]}

        symbols = build_global_symbols(env)

        assert "env.name.value" not in symbols

    def test_policy_capability_registers_base_symbol(self) -> None:
        symbols = build_global_symbols({"variables": [_policy_variable()]})

        assert symbols["env.ccm_usage_policy"]["source"] == "env.variables"

    def test_policy_capability_exposes_returns_subfield(self) -> None:
        symbols = build_global_symbols({"variables": [_policy_variable()]})

        policy_symbol = symbols["env.ccm_usage_policy.policy"]

        assert policy_symbol["type"] == "object"
        assert policy_symbol["class"] == "Policy"

    def test_legacy_mapping_form_still_supported(self) -> None:
        env = {"variables": {"region": "eu", "retries": 3}}

        symbols = build_global_symbols(env)

        assert symbols["env.region"]["type"] == "string"
        assert symbols["env.retries"]["type"] == "integer"

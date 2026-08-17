#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Round-trip and back-compat tests for the verb-form variable syntax (LOCKED GRAMMAR v1)."""

from __future__ import annotations

import yaml

from tractusx_testlab.compiler.validation._expressions import resolve_expression
from tractusx_testlab.models import VariableSource
from tractusx_testlab.scripting._builders import parse_variables

# A variables block in YAML can be a verb-form LIST (id-keyed) or a legacy MAP.
_PROVIDE_NOW = """
- id: consumer_bpn
  uses: variable/type/string
  with:
    value: BPNL0000000TEST
  returns:
    value:
      type: string
"""

_ASK_OPERATOR = """
- id: operator_token
  uses: variable/type/string
  with:
    source: input
    placeholder: "Paste the bearer token"
  returns:
    value:
      type: string
"""

_GENERATED = """
- id: provider_bpn
  uses: generate/bpn
  with: {}
  returns:
    value:
      type: string
      format: bpn
"""


def _parse(yaml_text: str) -> dict:
    return parse_variables(yaml.safe_load(yaml_text))


def test_parses_simple_provide_now_verb_form() -> None:
    # Arrange / Act
    variables = _parse(_PROVIDE_NOW)

    # Assert
    var = variables["consumer_bpn"]
    assert var.name == "consumer_bpn"
    assert var.type == "string"
    assert var.default == "BPNL0000000TEST"
    assert var.source is VariableSource.VALUE
    assert var.generator is None


def test_parses_ask_operator_verb_form() -> None:
    # Arrange / Act
    variables = _parse(_ASK_OPERATOR)

    # Assert
    var = variables["operator_token"]
    assert var.source is VariableSource.INPUT
    assert var.placeholder == "Paste the bearer token"
    assert var.default is None
    assert var.runtime is True


def test_parses_generated_verb_form() -> None:
    # Arrange / Act
    variables = _parse(_GENERATED)

    # Assert
    var = variables["provider_bpn"]
    assert var.source is VariableSource.GENERATED
    assert var.generator == "bpn"
    assert var.type == "string"
    assert var.format == "bpn"


def test_legacy_flat_scalar_still_parses() -> None:
    # Arrange
    block = {"counter_party_bpn": "BPNL00000003AYRE"}

    # Act
    variables = parse_variables(block)

    # Assert — back-compat: flat name: value is unchanged
    var = variables["counter_party_bpn"]
    assert var.default == "BPNL00000003AYRE"
    assert var.source is VariableSource.VALUE


def test_legacy_type_default_mapping_still_parses() -> None:
    # Arrange
    block = {"retries": {"type": "integer", "default": 3, "runtime": True}}

    # Act
    variables = parse_variables(block)

    # Assert — back-compat: {type, default} mapping is unchanged
    var = variables["retries"]
    assert var.type == "integer"
    assert var.default == 3
    assert var.runtime is True


def test_map_of_verb_entries_still_parses() -> None:
    # Arrange — verb form expressed as a name-keyed map (no list)
    block = {
        "asset_id": {
            "uses": "generate/uuid_v4",
            "with": {},
            "returns": {"value": {"type": "string"}},
        }
    }

    # Act
    variables = parse_variables(block)

    # Assert
    var = variables["asset_id"]
    assert var.source is VariableSource.GENERATED
    assert var.generator == "uuid_v4"


def test_env_reference_resolves_for_verb_form_variable() -> None:
    # Arrange
    variables = _parse(_PROVIDE_NOW)

    # Act
    resolved = resolve_expression("${{ env.consumer_bpn }}")

    # Assert — the addressable name is the entry id, so env.<id> resolves
    assert "consumer_bpn" in variables
    assert resolved == {"$ref": "env.consumer_bpn"}

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

"""Tests for the type an ``env`` variable declares deciding what the run is seeded with."""

from __future__ import annotations

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition
from tractusx_testlab.models.primitives.exceptions import VariableTypeError
from tractusx_testlab.player.execution._context_seeder import (
    seed_context_variables,
    seed_env_variables,
)
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.scripting.script import Tck
from tractusx_testlab.services.instances import ServiceManager

_POLICY_JSON = """
{
  "permission": [{"action": "use", "constraint": []}],
  "prohibition": [],
  "obligation": []
}
"""

_POLICY_DOC = {
    "permission": [{"action": "use", "constraint": []}],
    "prohibition": [],
    "obligation": [],
}


def _tck(*variables: dict) -> Tck:
    return Tck(
        TckDefinition(
            kind="tck",
            syntax="v1-alpha",
            id="variable-types-tck",
            metadata=TckMetadataDefinition(name="Variable types", version="1.0"),
            env={"variables": list(variables)},
        )
    )


def _variable(var_id: str, uses: str, value: object, returns: dict) -> dict:
    return {"id": var_id, "uses": uses, "with": {"value": value}, "returns": returns}


def _policy(value: object, returns: dict | None = None) -> dict:
    return _variable(
        "usage_policy",
        "config/connector/policy",
        value,
        {"value": {"type": "object", "class": "Policy"}} if returns is None else returns,
    )


def _context() -> StepContext:
    return StepContext(
        services=ServiceManager(),
        job=Job(job_id="variable-types-test"),
        config=TestlabConfig(),
    )


class TestDeclaredTypeDecides:
    """``returns.<key>.type`` is what the variable publishes, not what YAML wrote."""

    def test_json_text_declared_object_is_seeded_as_a_document(self) -> None:
        """A ``value: |`` block under ``type: object`` used to be seeded as its text."""
        context = _context()

        seed_env_variables(context, _tck(_policy(_POLICY_JSON)))

        assert context.get_variable("usage_policy") == _POLICY_DOC

    def test_the_id_is_the_only_name_the_variable_answers_to(self) -> None:
        """``env.usage_policy.policy`` was a second name for what ``env.usage_policy`` is."""
        context = _context()

        seed_env_variables(context, _tck(_policy(_POLICY_JSON)))

        assert not [name for name in context.variables if name.startswith("usage_policy.")]

    def test_yaml_text_declared_object_is_seeded_as_a_document(self) -> None:
        """A block unindented one level too far says the same thing a pasted JSON one does."""
        context = _context()
        yaml_text = (
            "permission:\n  - action: use\n    constraint: []\nprohibition: []\nobligation: []\n"
        )

        seed_env_variables(context, _tck(_policy(yaml_text)))

        assert context.get_variable("usage_policy") == _POLICY_DOC

    def test_a_value_written_as_yaml_is_untouched(self) -> None:
        context = _context()

        seed_env_variables(context, _tck(_policy(_POLICY_DOC)))

        assert context.get_variable("usage_policy") == _POLICY_DOC

    def test_the_verb_decides_the_type_not_the_returns_block(self) -> None:
        """A 'config/connector/policy' publishes an object however its declaration reads."""
        context = _context()

        seed_env_variables(context, _tck(_policy(_POLICY_JSON, returns={})))

        assert context.get_variable("usage_policy") == _POLICY_DOC

    def test_json_text_declared_array_is_seeded_as_a_list(self) -> None:
        context = _context()

        seed_env_variables(
            context,
            _tck(
                _variable("filters", "variable/type/array", "[1, 2]", {"value": {"type": "array"}})
            ),
        )

        assert context.get_variable("filters") == [1, 2]

    def test_a_string_variable_holding_json_stays_text(self) -> None:
        """Only a declared structure coerces — a filter the SUT takes as text is text."""
        context = _context()
        filter_text = '[{"name":"digitalTwinType","value":"PartType"}]'

        seed_env_variables(
            context,
            _tck(
                _variable(
                    "digital_twin_type_filter",
                    "variable/type/string",
                    filter_text,
                    {"value": {"type": "string"}},
                )
            ),
        )

        assert context.get_variable("digital_twin_type_filter") == filter_text

    def test_an_unknown_verb_falls_back_to_the_declared_type(self) -> None:
        """The compiler refuses one; a player handed an unvalidated TCK reads its word."""
        context = _context()

        seed_env_variables(
            context,
            _tck(
                _variable("loose", "variable/type/unheard-of", "{}", {"value": {"type": "object"}})
            ),
        )

        assert context.get_variable("loose") == {}


class TestTypeMismatchIsRefused:
    """A structure declared and not supplied is an authoring error, not a string."""

    def test_text_that_is_neither_json_nor_yaml_is_refused(self) -> None:
        with pytest.raises(VariableTypeError) as error:
            seed_env_variables(_context(), _tck(_policy('{"permission": [}')))
        message = str(error.value)
        assert "usage_policy" in message
        assert "type: object" in message

    def test_text_that_parses_to_a_scalar_is_refused(self) -> None:
        """Prose in a block scalar is valid YAML and is still not a policy."""
        with pytest.raises(VariableTypeError) as error:
            seed_env_variables(_context(), _tck(_policy("the usual usage policy")))
        assert "reads as str" in str(error.value)

    def test_a_structure_of_the_wrong_shape_is_refused(self) -> None:
        with pytest.raises(VariableTypeError) as error:
            seed_env_variables(_context(), _tck(_policy("[1, 2]")))
        assert "reads as list" in str(error.value)


class TestOperatorOverrides:
    """A ``--var`` override is the same variable the manifest declared."""

    def test_an_override_is_read_as_the_declared_type(self) -> None:
        context = _context()

        seed_context_variables(
            context,
            _tck(_policy(_POLICY_DOC)),
            {"usage_policy": _POLICY_JSON},
        )

        assert context.get_variable("usage_policy") == _POLICY_DOC

    def test_an_override_of_an_undeclared_name_is_passed_through(self) -> None:
        context = _context()

        seed_context_variables(
            context, _tck(), {"infrastructure.sut.connector.dsp_url": "https://x"}
        )

        assert context.get_variable("infrastructure.sut.connector.dsp_url") == "https://x"

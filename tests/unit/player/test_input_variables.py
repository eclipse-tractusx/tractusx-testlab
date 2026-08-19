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

"""Tests for the input variables a TCK declares and the operator must supply."""

from __future__ import annotations

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job
from tractusx_testlab.models.authoring.definitions import (
    TckDefinition,
    TckMetadataDefinition,
)
from tractusx_testlab.models.primitives.binding_errors import MissingInputVariableError
from tractusx_testlab.player.execution._context_seeder import require_inputs
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.scripting.script import Tck
from tractusx_testlab.services.instances import ServiceManager


def _tck(*variables: dict) -> Tck:
    return Tck(
        TckDefinition(
            kind="tck",
            syntax="v1-alpha",
            id="inputs-tck",
            metadata=TckMetadataDefinition(name="Inputs", version="1.0"),
            env={"variables": list(variables)},
        )
    )


def _input(var_id: str, description: str | None = None) -> dict:
    entry: dict = {
        "id": var_id,
        "uses": "variable/type/string",
        "with": {"source": "input"},
        "returns": {"value": {"type": "string"}},
    }
    if description is not None:
        entry["description"] = description
    return entry


def _literal(var_id: str, value: str) -> dict:
    return {
        "id": var_id,
        "uses": "variable/type/string",
        "with": {"value": value},
        "returns": {"value": {"type": "string"}},
    }


def _context() -> StepContext:
    return StepContext(
        services=ServiceManager(),
        job=Job(job_id="inputs-test"),
        config=TestlabConfig(),
    )


class TestRequireInputs:
    """An input the TCK cannot invent is asked for before the run, not during it."""

    def test_a_supplied_input_is_accepted(self) -> None:
        context = _context()
        context.set_variable("shell_descriptor_id", "urn:uuid:1234")

        require_inputs(context, _tck(_input("shell_descriptor_id")))

    def test_an_unsupplied_input_is_refused(self) -> None:
        with pytest.raises(MissingInputVariableError) as error:
            require_inputs(_context(), _tck(_input("shell_descriptor_id")))
        assert "shell_descriptor_id" in str(error.value)

    def test_every_unsupplied_input_is_named_at_once(self) -> None:
        """One run tells the operator the whole list, not the first name in it."""
        with pytest.raises(MissingInputVariableError) as error:
            require_inputs(_context(), _tck(_input("valid_bpn"), _input("counter_party_id")))
        message = str(error.value)
        assert "valid_bpn" in message
        assert "counter_party_id" in message

    def test_a_variable_carrying_its_own_value_is_not_owed(self) -> None:
        """Only ``source: input`` is a question for the operator."""
        require_inputs(_context(), _tck(_literal("page_size", "10")))

    def test_the_declared_description_is_shown_beside_the_name(self) -> None:
        """What the value is for is the part that makes the list actionable."""
        with pytest.raises(MissingInputVariableError) as error:
            require_inputs(
                _context(),
                _tck(_input("shell_descriptor_id", "AAS id of the twin under test")),
            )
        assert "AAS id of the twin under test" in str(error.value)

    def test_a_blank_value_counts_as_unsupplied(self) -> None:
        """An empty string in a config is a key someone meant to fill in."""
        context = _context()
        context.set_variable("valid_bpn", "   ")

        with pytest.raises(MissingInputVariableError):
            require_inputs(context, _tck(_input("valid_bpn")))

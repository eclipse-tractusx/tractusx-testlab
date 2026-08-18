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

"""Tests for util/validate_path."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps.util.validate_path import ValidatePathStep


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinition:
    return StepDefinition(id="check", uses="util/validate_path")


class TestValidatePathStep:
    def test_registered_under_its_own_uses_key(self) -> None:
        assert StepRegistry.get("util/validate_path", "saturn") is ValidatePathStep

    @pytest.mark.asyncio
    async def test_extracts_value_by_variable_and_path(self, context: StepContext) -> None:
        context.set_variable("response_body", {"content": {"status": "READY"}})
        output = await ValidatePathStep().invoke(
            {"input": "response_body", "path": "content.status"},
            context,
            _definition(),
        )
        assert output.value == "READY"

    @pytest.mark.asyncio
    async def test_missing_variable_raises(self, context: StepContext) -> None:
        with pytest.raises(KeyError, match="not found"):
            await ValidatePathStep().invoke(
                {"input": "does_not_exist", "path": "a.b"},
                context,
                _definition(),
            )

#################################################################################
# Eclipse Tractus-X - Software Development KIT
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

"""Tests for util/generate_bpn."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.utility.generate_bpn import (
    GenerateBpnOutput,
    GenerateBpnParams,
    GenerateBpnStep,
)


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinitionV2:
    return StepDefinitionV2(id="gen", uses="util/generate_bpn")


class TestGenerateBpnStep:
    @pytest.mark.asyncio
    async def test_defaults_to_bpnl_prefix(self, context: StepContext) -> None:
        output = await GenerateBpnStep().invoke({}, context, _definition())
        assert output.value["bpn"].startswith("BPNL")

    @pytest.mark.asyncio
    async def test_generated_bpn_has_16_chars(self, context: StepContext) -> None:
        output = await GenerateBpnStep().invoke({}, context, _definition())
        assert len(output.value["bpn"]) == 16

    @pytest.mark.asyncio
    async def test_accepts_bpns_prefix(self, context: StepContext) -> None:
        output = await GenerateBpnStep().invoke({"prefix": "BPNS"}, context, _definition())
        assert output.value["bpn"].startswith("BPNS")

    @pytest.mark.asyncio
    async def test_accepts_bpna_prefix_lowercase(self, context: StepContext) -> None:
        output = await GenerateBpnStep().invoke({"prefix": "bpna"}, context, _definition())
        assert output.value["bpn"].startswith("BPNA")

    @pytest.mark.asyncio
    async def test_rejects_invalid_prefix(self, context: StepContext) -> None:
        step, definition = GenerateBpnStep(), _definition()
        with pytest.raises(ValueError, match="Invalid parameters for step 'util/generate_bpn'"):
            await step.invoke({"prefix": "XXXX"}, context, definition)

    @pytest.mark.asyncio
    async def test_two_calls_produce_different_bpns(self, context: StepContext) -> None:
        first = await GenerateBpnStep().invoke({}, context, _definition())
        second = await GenerateBpnStep().invoke({}, context, _definition())
        assert first.value["bpn"] != second.value["bpn"]

    @pytest.mark.asyncio
    async def test_output_is_plain_data_not_a_model(self, context: StepContext) -> None:
        output = await GenerateBpnStep().invoke({}, context, _definition())
        assert isinstance(output.value, dict)

    @pytest.mark.asyncio
    async def test_unknown_params_are_tolerated(self, context: StepContext) -> None:
        output = await GenerateBpnStep().invoke({"unknown": 1}, context, _definition())
        assert output.value["bpn"].startswith("BPNL")


class TestGenerateBpnContract:
    def test_step_declares_its_models(self) -> None:
        assert GenerateBpnStep.params_model is GenerateBpnParams
        assert GenerateBpnStep.output_model is GenerateBpnOutput

    def test_step_type_is_stamped_by_the_registry(self) -> None:
        assert GenerateBpnStep.step_type == "util/generate_bpn"

    def test_describe_exposes_input_schema(self) -> None:
        contract = GenerateBpnStep.describe()
        assert contract.params_schema is not None
        assert "prefix" in contract.params_schema["properties"]

    def test_describe_exposes_output_schema(self) -> None:
        contract = GenerateBpnStep.describe()
        assert contract.output_schema is not None
        assert "bpn" in contract.output_schema["properties"]

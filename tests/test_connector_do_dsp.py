################################################################################
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
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Unit tests for DoDspStep and DoDspWithBpnlStep."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.steps.connector.do_dsp import DoDspStep, DoDspWithBpnlStep
from tractusx_testlab.syntax.context_vars import DATAPLANE_ENDPOINT, EDR_TOKEN

_ENDPOINT = "https://provider.example.com/data"
_TOKEN = "Bearer eyJhbGciOiJSUzI1NiJ9.test"
_BASE_URL = "https://consumer.example.com"


@pytest.fixture()
def ctx() -> MagicMock:
    """StepContext mock with working variable store and consumer service."""
    mock = MagicMock()
    variables: dict[str, Any] = {}

    def _set(name: str, value: Any) -> None:
        variables[name] = value

    def _get(name: str, default: Any = None) -> Any:
        return variables.get(name, default)

    mock.set_variable = MagicMock(side_effect=_set)
    mock.get_variable = MagicMock(side_effect=_get)
    mock.variables = variables
    mock.get_consumer_base_url.return_value = _BASE_URL
    return attach_endpoint_url_stubs(mock)


@pytest.fixture()
def definition() -> MagicMock:
    return MagicMock()


class TestDoDspStep:
    """Tests for DoDspStep — full DSP flow via SDK consumer.do_dsp()."""

    @pytest.mark.asyncio
    async def test_stores_endpoint_and_token_in_context(self, ctx: MagicMock, definition: MagicMock) -> None:
        # Arrange
        consumer = MagicMock()
        consumer.do_dsp.return_value = (_ENDPOINT, _TOKEN)
        ctx.get_consumer_service.return_value = consumer

        # Act
        await DoDspStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
            },
            context=ctx,
            definition=definition,
        )

        # Assert — context variables
        assert ctx.variables[DATAPLANE_ENDPOINT] == _ENDPOINT
        assert ctx.variables[EDR_TOKEN] == _TOKEN

    @pytest.mark.asyncio
    async def test_output_value_contains_endpoint_and_token(self, ctx: MagicMock, definition: MagicMock) -> None:
        # Arrange
        consumer = MagicMock()
        consumer.do_dsp.return_value = (_ENDPOINT, _TOKEN)
        ctx.get_consumer_service.return_value = consumer

        # Act
        output = await DoDspStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
            },
            context=ctx,
            definition=definition,
        )

        # Assert — output shape
        assert output.value == {"endpoint": _ENDPOINT, "token": _TOKEN}

    @pytest.mark.asyncio
    async def test_status_200_on_success(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp.return_value = (_ENDPOINT, _TOKEN)
        ctx.get_consumer_service.return_value = consumer

        output = await DoDspStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
            },
            context=ctx,
            definition=definition,
        )

        assert output.response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_500_when_endpoint_is_none(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp.return_value = (None, None)
        ctx.get_consumer_service.return_value = consumer

        output = await DoDspStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
            },
            context=ctx,
            definition=definition,
        )

        assert output.response.status_code == 500

    @pytest.mark.asyncio
    async def test_passes_filter_expression_and_policies_to_sdk(self, ctx: MagicMock, definition: MagicMock) -> None:
        # Arrange
        consumer = MagicMock()
        consumer.do_dsp.return_value = (_ENDPOINT, _TOKEN)
        ctx.get_consumer_service.return_value = consumer
        filter_expr = [{"operandLeft": "edc:id", "operator": "=", "operandRight": "asset-1"}]
        policies = [{"@id": "policy-1"}]

        # Act
        await DoDspStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
                "filter_expression": filter_expr,
                "policies": policies,
            },
            context=ctx,
            definition=definition,
        )

        # Assert — SDK call carried the right arguments
        consumer.do_dsp.assert_called_once_with(
            counter_party_id="BPNL000000000001",
            counter_party_address="https://provider.example.com/dsp",
            filter_expression=filter_expr,
            policies=policies,
        )

    @pytest.mark.asyncio
    async def test_does_not_store_none_endpoint_in_context(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp.return_value = (None, None)
        ctx.get_consumer_service.return_value = consumer

        await DoDspStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
            },
            context=ctx,
            definition=definition,
        )

        assert DATAPLANE_ENDPOINT not in ctx.variables
        assert EDR_TOKEN not in ctx.variables


class TestDoDspWithBpnlStep:
    """Tests for DoDspWithBpnlStep — BPNL-based DSP flow via SDK consumer.do_dsp_with_bpnl()."""

    @pytest.mark.asyncio
    async def test_stores_endpoint_and_token_in_context(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_with_bpnl.return_value = (_ENDPOINT, _TOKEN)
        ctx.get_consumer_service.return_value = consumer

        output = await DoDspWithBpnlStep().invoke(
            raw_params={"bpnl": "BPNL000000000001"},
            context=ctx,
            definition=definition,
        )

        assert ctx.variables[DATAPLANE_ENDPOINT] == _ENDPOINT
        assert ctx.variables[EDR_TOKEN] == _TOKEN
        assert output.value == {"endpoint": _ENDPOINT, "token": _TOKEN}
        assert output.response.status_code == 200

    @pytest.mark.asyncio
    async def test_passes_bpnl_and_optional_params_to_sdk(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_with_bpnl.return_value = (_ENDPOINT, _TOKEN)
        ctx.get_consumer_service.return_value = consumer
        filter_expr = [{"operandLeft": "edc:id", "operator": "=", "operandRight": "asset-2"}]

        await DoDspWithBpnlStep().invoke(
            raw_params={
                "bpnl": "BPNL000000000002",
                "counter_party_address": "https://provider.example.com/dsp",
                "filter_expression": filter_expr,
                "policies": None,
            },
            context=ctx,
            definition=definition,
        )

        consumer.do_dsp_with_bpnl.assert_called_once_with(
            bpnl="BPNL000000000002",
            counter_party_address="https://provider.example.com/dsp",
            filter_expression=filter_expr,
            policies=None,
        )

    @pytest.mark.asyncio
    async def test_status_500_when_endpoint_is_none(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_with_bpnl.return_value = (None, None)
        ctx.get_consumer_service.return_value = consumer

        output = await DoDspWithBpnlStep().invoke(
            raw_params={"bpnl": "BPNL000000000001"},
            context=ctx,
            definition=definition,
        )

        assert output.response.status_code == 500

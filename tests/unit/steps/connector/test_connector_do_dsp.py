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

"""Unit tests for DoDspStep, DoDspWithBpnlStep, and DiscoverDtrAuthStep."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.models import StepExecutionError
from tractusx_testlab.steps.connector.do_dsp import (
    DTR_DCT_TYPE,
    DiscoverDtrAuthStep,
    DoDspStep,
    DoDspWithBpnlStep,
)
from tractusx_testlab.syntax.context_vars import DATAPLANE_URL, EDR_TOKEN

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
    mock.get_str = MagicMock(side_effect=lambda n, d="": str(_get(n, d) or d))
    mock.variables = variables
    mock.dataspace.consumer_base_url.return_value = _BASE_URL
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
        ctx.dataspace.consumer.return_value = consumer

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
        assert ctx.variables[DATAPLANE_URL] == _ENDPOINT
        assert ctx.variables[EDR_TOKEN] == _TOKEN

    @pytest.mark.asyncio
    async def test_output_value_contains_endpoint_and_token(self, ctx: MagicMock, definition: MagicMock) -> None:
        # Arrange
        consumer = MagicMock()
        consumer.do_dsp.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer

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
        assert output.value == {"dataplane_url": _ENDPOINT, "edr_token": _TOKEN}

    @pytest.mark.asyncio
    async def test_status_200_on_success(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer

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
    async def test_a_flow_without_an_endpoint_fails_the_step(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        """A DSP flow that produced no endpoint fails, rather than reporting a 500.

        The status was invented — the counterpart never sent one — and the
        runner recorded the step as PASSED, because a step fails only on a
        raise or a hard assertion.
        """
        consumer = MagicMock()
        consumer.do_dsp.return_value = (None, None)
        ctx.dataspace.consumer.return_value = consumer

        with pytest.raises(StepExecutionError, match="endpoint"):
            await DoDspStep().invoke(
                raw_params={
                    "counter_party_id": "BPNL000000000001",
                    "counter_party_address": "https://provider.example.com/dsp",
                },
                context=ctx,
                definition=definition,
            )

    @pytest.mark.asyncio
    async def test_passes_filter_expression_and_policies_to_sdk(self, ctx: MagicMock, definition: MagicMock) -> None:
        # Arrange
        consumer = MagicMock()
        consumer.do_dsp.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer
        filter_expr = [{"operand_left": "edc:id", "operator": "=", "operand_right": "asset-1"}]
        sdk_filter_expr = [{"operandLeft": "edc:id", "operator": "=", "operandRight": "asset-1"}]
        policies = [{"@id": "policy-1"}]

        # Act
        await DoDspStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
                "filters": filter_expr,
                "expected_policies": policies,
            },
            context=ctx,
            definition=definition,
        )

        # Assert — SDK call carried the right arguments
        consumer.do_dsp.assert_called_once_with(
            counter_party_id="BPNL000000000001",
            counter_party_address="https://provider.example.com/dsp",
            filter_expression=sdk_filter_expr,
            policies=policies,
        )

    @pytest.mark.asyncio
    async def test_does_not_store_none_endpoint_in_context(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp.return_value = (None, None)
        ctx.dataspace.consumer.return_value = consumer

        with pytest.raises(StepExecutionError):
            await DoDspStep().invoke(
                raw_params={
                    "counter_party_id": "BPNL000000000001",
                    "counter_party_address": "https://provider.example.com/dsp",
                },
                context=ctx,
                definition=definition,
            )

        assert DATAPLANE_URL not in ctx.variables
        assert EDR_TOKEN not in ctx.variables


class TestDoDspWithBpnlStep:
    """Tests for DoDspWithBpnlStep — BPNL-based DSP flow via SDK consumer.do_dsp_with_bpnl()."""

    @pytest.mark.asyncio
    async def test_stores_endpoint_and_token_in_context(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_with_bpnl.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer

        output = await DoDspWithBpnlStep().invoke(
            raw_params={"bpnl": "BPNL000000000001"},
            context=ctx,
            definition=definition,
        )

        assert ctx.variables[DATAPLANE_URL] == _ENDPOINT
        assert ctx.variables[EDR_TOKEN] == _TOKEN
        assert output.value == {"dataplane_url": _ENDPOINT, "edr_token": _TOKEN}
        assert output.response.status_code == 200

    @pytest.mark.asyncio
    async def test_passes_bpnl_and_optional_params_to_sdk(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_with_bpnl.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer
        filter_expr = [{"operand_left": "edc:id", "operator": "=", "operand_right": "asset-2"}]
        sdk_filter_expr = [{"operandLeft": "edc:id", "operator": "=", "operandRight": "asset-2"}]

        await DoDspWithBpnlStep().invoke(
            raw_params={
                "bpnl": "BPNL000000000002",
                "counter_party_address": "https://provider.example.com/dsp",
                "filters": filter_expr,
                "expected_policies": None,
            },
            context=ctx,
            definition=definition,
        )

        consumer.do_dsp_with_bpnl.assert_called_once_with(
            bpnl="BPNL000000000002",
            counter_party_address="https://provider.example.com/dsp",
            filter_expression=sdk_filter_expr,
            policies=None,
        )

    @pytest.mark.asyncio
    async def test_a_flow_without_an_endpoint_fails_the_step(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        """A DSP flow that produced no endpoint fails, rather than reporting a 500.

        The status was invented — the counterpart never sent one — and the
        runner recorded the step as PASSED, because a step fails only on a
        raise or a hard assertion.
        """
        consumer = MagicMock()
        consumer.do_dsp_with_bpnl.return_value = (None, None)
        ctx.dataspace.consumer.return_value = consumer

        with pytest.raises(StepExecutionError, match="endpoint"):
            await DoDspWithBpnlStep().invoke(
                raw_params={"bpnl": "BPNL000000000001"},
                context=ctx,
                definition=definition,
            )


class TestDiscoverDtrAuthStep:
    """Tests for DiscoverDtrAuthStep — DTR access via SDK consumer.do_dsp_by_dct_type()."""

    @pytest.mark.asyncio
    async def test_stores_endpoint_and_token_in_context(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_by_dct_type.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer

        output = await DiscoverDtrAuthStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
            },
            context=ctx,
            definition=definition,
        )

        assert ctx.variables[DATAPLANE_URL] == _ENDPOINT
        assert ctx.variables[EDR_TOKEN] == _TOKEN
        assert output.value == {"dataplane_url": _ENDPOINT, "edr_token": _TOKEN}
        assert output.response.status_code == 200

    @pytest.mark.asyncio
    async def test_filters_by_the_standard_dct_type_by_default(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_by_dct_type.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer

        await DiscoverDtrAuthStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider.example.com/dsp",
            },
            context=ctx,
            definition=definition,
        )

        consumer.do_dsp_by_dct_type.assert_called_once_with(
            counter_party_id="BPNL000000000001",
            counter_party_address="https://provider.example.com/dsp",
            dct_type=DTR_DCT_TYPE,
            policies=None,
        )

    @pytest.mark.asyncio
    async def test_passes_overridden_dct_type_and_policies_to_sdk(self, ctx: MagicMock, definition: MagicMock) -> None:
        consumer = MagicMock()
        consumer.do_dsp_by_dct_type.return_value = (_ENDPOINT, _TOKEN)
        ctx.dataspace.consumer.return_value = consumer
        policies = [{"@id": "policy-1"}]

        await DiscoverDtrAuthStep().invoke(
            raw_params={
                "counter_party_id": "BPNL000000000002",
                "counter_party_address": "https://provider.example.com/dsp",
                "dct_type": "https://w3id.org/catenax/taxonomy#OTHER",
                "expected_policies": policies,
            },
            context=ctx,
            definition=definition,
        )

        consumer.do_dsp_by_dct_type.assert_called_once_with(
            counter_party_id="BPNL000000000002",
            counter_party_address="https://provider.example.com/dsp",
            dct_type="https://w3id.org/catenax/taxonomy#OTHER",
            policies=policies,
        )

    @pytest.mark.asyncio
    async def test_a_flow_without_an_endpoint_fails_the_step(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        """A DSP flow that produced no endpoint fails, rather than reporting a 500.

        The status was invented — the counterpart never sent one — and the
        runner recorded the step as PASSED, because a step fails only on a
        raise or a hard assertion.
        """
        consumer = MagicMock()
        consumer.do_dsp_by_dct_type.return_value = (None, None)
        ctx.dataspace.consumer.return_value = consumer

        with pytest.raises(StepExecutionError, match="endpoint"):
            await DiscoverDtrAuthStep().invoke(
                raw_params={
                    "counter_party_id": "BPNL000000000001",
                    "counter_party_address": "https://provider.example.com/dsp",
                },
                context=ctx,
                definition=definition,
            )
        assert DATAPLANE_URL not in ctx.variables
        assert EDR_TOKEN not in ctx.variables

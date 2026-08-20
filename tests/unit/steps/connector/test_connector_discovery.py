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

"""Tests for connector/consumer/discover_connector — the Saturn-only step."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition, StepExecutionError
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps.connector.discover_connector import (
    EDC_NAMESPACE,
    DiscoverConnectorStep,
)

_STEP = "connector/consumer/discover_connector"
_BPNL = "BPNL000000000001"

#: What a Saturn connector answers with, in the namespaced spelling.
_NAMESPACED = {
    f"{EDC_NAMESPACE}counterPartyAddress": "http://provider/api/v1/dsp",
    f"{EDC_NAMESPACE}counterPartyId": "BPNL000000000002",
    f"{EDC_NAMESPACE}protocol": "dataspace-protocol-http:2025-1",
}

#: The same answer, with the keys left bare.
_BARE = {
    "counterPartyAddress": "http://provider/api/v1/dsp",
    "counterPartyId": "BPNL000000000002",
    "protocol": "dataspace-protocol-http:2025-1",
}


def _definition() -> StepDefinition:
    return StepDefinition(id="discover", uses=_STEP)


def _with_consumer(context: MagicMock, consumer: MagicMock) -> MagicMock:
    context.dataspace.consumer.return_value = consumer
    context.dataspace.consumer_base_url.return_value = "http://consumer"
    return context


def _consumer(document: object) -> MagicMock:
    consumer = MagicMock()
    consumer.discover_connector_protocol.return_value = document
    return consumer


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestSaturnOnlyRegistration:
    def test_a_saturn_script_resolves_the_step(self) -> None:
        assert StepRegistry.get(_STEP, "saturn") is DiscoverConnectorStep

    def test_a_jupiter_script_does_not(self) -> None:
        """Jupiter connectors have no discovery endpoint, so the step is not offered."""
        assert StepRegistry.get(_STEP, "jupiter") is None

    def test_the_step_still_describes_itself_without_a_version(self) -> None:
        """Docs and the ``returns:`` check ask by name alone; the step must answer."""
        assert StepRegistry.get_any(_STEP) is DiscoverConnectorStep
        assert _STEP in StepRegistry.list_step_types()


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class TestDiscoverConnectorParams:
    def test_bpnl_is_required(self) -> None:
        with pytest.raises(ValueError, match="bpnl: required key 'bpnl' is missing"):
            DiscoverConnectorStep.bind_params({})

    def test_bind_params_error_names_the_step(self) -> None:
        with pytest.raises(ValueError, match=f"Invalid parameters for step '{_STEP}'"):
            DiscoverConnectorStep.bind_params({})

    def test_namespace_defaults_to_the_edc_one(self) -> None:
        assert DiscoverConnectorStep.bind_params({"bpnl": _BPNL}).namespace == EDC_NAMESPACE


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class TestDiscoverConnectorStep:
    @pytest.mark.asyncio
    async def test_namespaced_keys_are_read_out_of_the_response(
        self, mock_context: MagicMock
    ) -> None:
        output = await DiscoverConnectorStep().invoke(
            {"bpnl": _BPNL},
            _with_consumer(mock_context, _consumer(_NAMESPACED)),
            _definition(),
        )
        assert output.value["counter_party_address"] == "http://provider/api/v1/dsp"
        assert output.value["counter_party_id"] == "BPNL000000000002"
        assert output.value["protocol"] == "dataspace-protocol-http:2025-1"

    @pytest.mark.asyncio
    async def test_bare_keys_are_the_same_answer(self, mock_context: MagicMock) -> None:
        """A connector that does not expand the response has still answered."""
        output = await DiscoverConnectorStep().invoke(
            {"bpnl": _BPNL},
            _with_consumer(mock_context, _consumer(_BARE)),
            _definition(),
        )
        assert output.value["counter_party_address"] == "http://provider/api/v1/dsp"

    @pytest.mark.asyncio
    async def test_the_document_is_returned_unchanged(self, mock_context: MagicMock) -> None:
        output = await DiscoverConnectorStep().invoke(
            {"bpnl": _BPNL},
            _with_consumer(mock_context, _consumer(_NAMESPACED)),
            _definition(),
        )
        assert output.value["discovery"] == _NAMESPACED

    @pytest.mark.asyncio
    async def test_the_connector_is_discovered_once(self, mock_context: MagicMock) -> None:
        """Resolving three values and the document must not cost two round trips."""
        consumer = _consumer(_NAMESPACED)
        await DiscoverConnectorStep().invoke(
            {"bpnl": _BPNL}, _with_consumer(mock_context, consumer), _definition()
        )
        assert consumer.discover_connector_protocol.call_count == 1

    @pytest.mark.asyncio
    async def test_an_omitted_address_reaches_the_sdk_as_none(
        self, mock_context: MagicMock
    ) -> None:
        """The SDK reads ``None`` as "resolve it from the BPN", but not ``""``."""
        consumer = _consumer(_NAMESPACED)
        await DiscoverConnectorStep().invoke(
            {"bpnl": _BPNL}, _with_consumer(mock_context, consumer), _definition()
        )
        kwargs = consumer.discover_connector_protocol.call_args.kwargs
        assert kwargs == {"bpnl": _BPNL, "counter_party_address": None}

    @pytest.mark.asyncio
    async def test_a_given_address_is_passed_through(self, mock_context: MagicMock) -> None:
        consumer = _consumer(_NAMESPACED)
        await DiscoverConnectorStep().invoke(
            {"bpnl": _BPNL, "counter_party_address": "http://known/dsp"},
            _with_consumer(mock_context, consumer),
            _definition(),
        )
        assert (
            consumer.discover_connector_protocol.call_args.kwargs["counter_party_address"]
            == "http://known/dsp"
        )

    @pytest.mark.asyncio
    async def test_all_four_fields_are_published_for_later_steps(
        self, mock_context: MagicMock
    ) -> None:
        await DiscoverConnectorStep().invoke(
            {"bpnl": _BPNL},
            _with_consumer(mock_context, _consumer(_NAMESPACED)),
            _definition(),
        )
        assert mock_context.get_variable("counter_party_address") == "http://provider/api/v1/dsp"
        assert mock_context.get_variable("counter_party_id") == "BPNL000000000002"
        assert mock_context.get_variable("protocol") == "dataspace-protocol-http:2025-1"
        assert mock_context.get_variable("discovery") == _NAMESPACED

    @pytest.mark.asyncio
    async def test_a_missing_key_fails_the_step_naming_what_was_looked_for(
        self, mock_context: MagicMock
    ) -> None:
        """Publishing an empty endpoint would surface as a refused connection later."""
        consumer = _consumer({f"{EDC_NAMESPACE}counterPartyAddress": "http://p/dsp"})
        with pytest.raises(StepExecutionError, match="carries no 'counterPartyId'"):
            await DiscoverConnectorStep().invoke(
                {"bpnl": _BPNL}, _with_consumer(mock_context, consumer), _definition()
            )

    @pytest.mark.asyncio
    async def test_no_document_fails_the_step(self, mock_context: MagicMock) -> None:
        with pytest.raises(StepExecutionError, match="no discovery document"):
            await DiscoverConnectorStep().invoke(
                {"bpnl": _BPNL}, _with_consumer(mock_context, _consumer(None)), _definition()
            )

    @pytest.mark.asyncio
    async def test_a_non_saturn_service_is_named_as_the_reason(
        self, mock_context: MagicMock
    ) -> None:
        consumer = MagicMock(spec=[])  # a service without the discovery method
        with pytest.raises(StepExecutionError, match="Saturn-only"):
            await DiscoverConnectorStep().invoke(
                {"bpnl": _BPNL}, _with_consumer(mock_context, consumer), _definition()
            )

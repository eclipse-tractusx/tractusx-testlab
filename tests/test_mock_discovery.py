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

"""Tests for mock/discovery — the BPN Discovery Finder mock."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.server.mock_registry import clear_mocks, resolve_mock
from tractusx_testlab.steps.server.mock_discovery import MockDiscoveryStep

_DISCOVERY_PATH = "/api/administration/connectors/discovery"


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_mocks()
    yield
    clear_mocks()


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinitionV2:
    return StepDefinitionV2(id="discovery", uses="mock/discovery")


class TestMockDiscoveryStep:
    @pytest.mark.asyncio
    async def test_requires_id(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="id: Field required"):
            await MockDiscoveryStep().invoke({"mappings": {"BPNL1": "https://a"}}, context, _definition())

    @pytest.mark.asyncio
    async def test_requires_mappings(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="mappings: Field required"):
            await MockDiscoveryStep().invoke({"id": "disc1"}, context, _definition())

    @pytest.mark.asyncio
    async def test_dict_mappings_filtered_by_requested_bpns(self, context: StepContext) -> None:
        await MockDiscoveryStep().invoke(
            {"id": "disc1", "mappings": {"BPNL1": "https://a/dsp", "BPNL2": "https://b/dsp"}},
            context, _definition(),
        )
        mock = resolve_mock(
            _DISCOVERY_PATH, "POST", headers={}, query_params={}, body=["BPNL1"],
        )
        assert mock.status_code == 200
        assert mock.body == [{"bpn": "BPNL1", "connectorEndpoint": ["https://a/dsp"]}]

    @pytest.mark.asyncio
    async def test_list_mappings_accepted(self, context: StepContext) -> None:
        await MockDiscoveryStep().invoke(
            {
                "id": "disc1",
                "mappings": [{"bpn": "BPNL1", "endpoint": "https://a/dsp"}],
            },
            context, _definition(),
        )
        mock = resolve_mock(
            _DISCOVERY_PATH, "POST", headers={}, query_params={}, body={"bpns": ["BPNL1"]},
        )
        assert mock.body == [{"bpn": "BPNL1", "connectorEndpoint": ["https://a/dsp"]}]

    @pytest.mark.asyncio
    async def test_no_requested_bpns_returns_all_mappings(self, context: StepContext) -> None:
        await MockDiscoveryStep().invoke(
            {"id": "disc1", "mappings": {"BPNL1": "https://a/dsp"}}, context, _definition(),
        )
        mock = resolve_mock(_DISCOVERY_PATH, "POST", headers={}, query_params={}, body=None)
        assert mock.body == [{"bpn": "BPNL1", "connectorEndpoint": ["https://a/dsp"]}]

    @pytest.mark.asyncio
    async def test_unknown_bpn_is_dropped(self, context: StepContext) -> None:
        await MockDiscoveryStep().invoke(
            {"id": "disc1", "mappings": {"BPNL1": "https://a/dsp"}}, context, _definition(),
        )
        mock = resolve_mock(
            _DISCOVERY_PATH, "POST", headers={}, query_params={}, body=["BPNL_UNKNOWN"],
        )
        assert mock.body == []

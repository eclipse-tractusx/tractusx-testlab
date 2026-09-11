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

## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The two steps that discover on the way point discovery at the DSP root.

``query_catalog_by_bpnl`` and ``do_dsp_with_bpnl`` hand their address to the
SDK, which discovers with it before anything else. Given the versioned SUT
binding as it is, discovery asked for ``…/2025-1/.well-known/dspace-version``
and got 404 (E2E run 34633071862); the version path is what discovery puts
back, so it is dropped on the way in.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.catalog_query import QueryCatalogByBpnlStep
from tractusx_testlab.steps.connector.do_dsp import DoDspWithBpnlStep

_BPNL = "BPNL000000000001"
_VERSIONED = "http://provider-dsp.local/api/v1/dsp/2025-1"
_ROOT = "http://provider-dsp.local/api/v1/dsp"


@pytest.fixture()
def consumer() -> MagicMock:
    service = MagicMock()
    service.get_catalog_with_bpnl.return_value = {"dcat:dataset": []}
    service.do_dsp_with_bpnl.return_value = ("http://dataplane", "token")
    return service


@pytest.fixture()
def ctx(consumer: MagicMock) -> MagicMock:
    mock = attach_endpoint_url_stubs(MagicMock())
    mock.dataspace.consumer.return_value = consumer
    mock.dataspace.consumer_base_url.return_value = "http://consumer"
    return mock


class TestQueryCatalogByBpnl:
    @pytest.mark.asyncio
    async def test_the_versioned_binding_reaches_the_sdk_as_the_root(
        self, ctx: MagicMock, consumer: MagicMock
    ) -> None:
        await QueryCatalogByBpnlStep().invoke(
            {"bpnl": _BPNL, "counter_party_address": _VERSIONED},
            ctx,
            StepDefinition(id="q", uses="connector/consumer/query_catalog_by_bpnl"),
        )
        assert consumer.get_catalog_with_bpnl.call_args.kwargs["counter_party_address"] == _ROOT

    @pytest.mark.asyncio
    async def test_no_address_stays_none(self, ctx: MagicMock, consumer: MagicMock) -> None:
        await QueryCatalogByBpnlStep().invoke(
            {"bpnl": _BPNL},
            ctx,
            StepDefinition(id="q", uses="connector/consumer/query_catalog_by_bpnl"),
        )
        assert consumer.get_catalog_with_bpnl.call_args.kwargs["counter_party_address"] is None


class TestDoDspWithBpnl:
    @pytest.mark.asyncio
    async def test_the_versioned_binding_reaches_the_sdk_as_the_root(
        self, ctx: MagicMock, consumer: MagicMock
    ) -> None:
        await DoDspWithBpnlStep().invoke(
            {"bpnl": _BPNL, "counter_party_address": _VERSIONED},
            ctx,
            StepDefinition(id="d", uses="connector/consumer/do_dsp_with_bpnl"),
        )
        assert consumer.do_dsp_with_bpnl.call_args.kwargs["counter_party_address"] == _ROOT

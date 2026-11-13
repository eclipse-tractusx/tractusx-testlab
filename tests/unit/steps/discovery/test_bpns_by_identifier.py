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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Tests for discovery/bpns_by_identifier — built on the SDK's BpnDiscoveryService."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.logging.masking import forget_secrets
from tractusx_testlab.models import BoundServiceError, StepDefinition, StepExecutionError
from tractusx_testlab.models.domain.discovery_capability import DiscoveryBinding
from tractusx_testlab.models.domain.infrastructure import EngineBindings, Infrastructure
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.discovery.bpns import BpnsByIdentifierStep

_STEP = "discovery/bpns_by_identifier"
_FINDER = "https://finder.example/api/v1.0/administration/connectors/discovery/search"
_BPN_DISCOVERY = "https://bpn-discovery.example"
_SEARCH = f"{_BPN_DISCOVERY}/api/v1.0/administration/connectors/bpnDiscovery/search"

#: The SDK's transports: the finder posts plainly, the BPN Discovery through a session.
_DO_POST = "tractusx_sdk.dataspace.tools.http_tools.HttpTools.do_post"
_DO_POST_SESSION = "tractusx_sdk.dataspace.tools.http_tools.HttpTools.do_post_with_session"

_FINDER_ANSWER = {
    "endpoints": [
        {"type": "bpn", "endpointAddress": "https://edc-discovery.example"},
        {"type": "manufacturerPartId", "endpointAddress": _BPN_DISCOVERY},
    ]
}


@pytest.fixture(autouse=True)
def _forget() -> None:
    yield
    forget_secrets()


def _answer(body: Any, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body
    return response


def _context(**binding: str) -> StepContext:
    job = MagicMock()
    job.job_id = "run-1"
    return StepContext(
        services=MagicMock(),
        job=job,
        config=MagicMock(),
        infrastructure=Infrastructure(engine=EngineBindings(discovery=DiscoveryBinding(**binding))),
    )


def _definition() -> StepDefinition:
    return StepDefinition(id="bpns", uses=_STEP)


def _found(*pairs: tuple[str, str]) -> dict[str, Any]:
    return {
        "bpns": [
            {"type": "manufacturerPartId", "key": key, "value": bpn, "resourceId": "r"}
            for key, bpn in pairs
        ]
    }


class TestRegistration:
    def test_registered_for_every_release(self) -> None:
        assert StepRegistry.get(_STEP, "saturn") is not None
        assert StepRegistry.get(_STEP, "jupiter") is not None


class TestLookup:
    @pytest.mark.asyncio
    async def test_finder_then_bpn_discovery_through_the_sdk(self) -> None:
        with patch(_DO_POST) as finder, patch(_DO_POST_SESSION) as search:
            finder.return_value = _answer(_FINDER_ANSWER)
            search.return_value = _answer(
                _found(
                    ("MPN-1", "BPNL000000000002"),
                    ("MPN-2", "BPNL000000000001"),
                    ("MPN-3", "BPNL000000000002"),
                )
            )
            out = await BpnsByIdentifierStep().invoke(
                {"keys": ["MPN-1", "MPN-2", "MPN-3"]}, _context(finder_url=_FINDER), _definition()
            )

        assert finder.call_args.kwargs["url"] == _FINDER
        assert finder.call_args.kwargs["json"] == {"types": ["manufacturerPartId"]}
        assert search.call_args.kwargs["url"] == _SEARCH
        assert search.call_args.kwargs["json"] == {
            "searchFilter": [{"type": "manufacturerPartId", "keys": ["MPN-1", "MPN-2", "MPN-3"]}]
        }
        # Once each and sorted: the SDK answers a set.
        assert out.value["bpns"] == ["BPNL000000000001", "BPNL000000000002"]
        assert out.value["bpnl"] == "BPNL000000000001"
        assert out.value["bpn_discovery_url"].startswith(_BPN_DISCOVERY)

    @pytest.mark.asyncio
    async def test_one_key_and_another_type(self) -> None:
        with patch(_DO_POST) as finder, patch(_DO_POST_SESSION) as search:
            finder.return_value = _answer(
                {"endpoints": [{"type": "serialNumber", "endpointAddress": _BPN_DISCOVERY}]}
            )
            search.return_value = _answer(_found(("SN-1", "BPNL000000000003")))
            out = await BpnsByIdentifierStep().invoke(
                {"keys": "SN-1", "identifier_type": "serialNumber"},
                _context(finder_url=_FINDER),
                _definition(),
            )
        assert search.call_args.kwargs["json"]["searchFilter"] == [
            {"type": "serialNumber", "keys": ["SN-1"]}
        ]
        assert out.value["bpnl"] == "BPNL000000000003"


class TestFailures:
    @pytest.mark.asyncio
    async def test_nothing_to_ask(self) -> None:
        with pytest.raises(StepExecutionError, match="no Discovery Finder to ask"):
            await BpnsByIdentifierStep().invoke({"keys": ["MPN-1"]}, _context(), _definition())

    @pytest.mark.asyncio
    async def test_unknown_identifier_fails_naming_the_service(self) -> None:
        with patch(_DO_POST) as finder, patch(_DO_POST_SESSION) as search:
            finder.return_value = _answer(_FINDER_ANSWER)
            search.return_value = _answer({"bpns": []})
            with pytest.raises(
                StepExecutionError, match="holds no BPN for manufacturerPartId 'MPN-9'"
            ):
                await BpnsByIdentifierStep().invoke(
                    {"keys": ["MPN-9"]}, _context(finder_url=_FINDER), _definition()
                )

    @pytest.mark.asyncio
    async def test_unauthorized_is_the_infrastructures_fault(self) -> None:
        with patch(_DO_POST) as finder, patch(_DO_POST_SESSION) as search:
            finder.return_value = _answer(_FINDER_ANSWER)
            search.return_value = _answer({}, 401)
            with pytest.raises(BoundServiceError, match="Unauthorized"):
                await BpnsByIdentifierStep().invoke(
                    {"keys": ["MPN-1"]}, _context(finder_url=_FINDER), _definition()
                )

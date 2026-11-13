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

"""Tests for discovery/connectors_by_bpn — built on the SDK's discovery services."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.logging.masking import forget_secrets, mask
from tractusx_testlab.models import BoundServiceError, StepDefinition, StepExecutionError
from tractusx_testlab.models.domain.discovery_capability import DiscoveryBinding
from tractusx_testlab.models.domain.infrastructure import EngineBindings, Infrastructure
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.discovery.connectors import ConnectorsByBpnStep

_STEP = "discovery/connectors_by_bpn"
_BPNL = "BPNL000000000001"
_FINDER = "https://finder.example/api/v1.0/administration/connectors/discovery/search"
_EDC_DISCOVERY = "https://edc-discovery.example/api/v1.0/administration/connectors/discovery"
_DSP = "https://provider.example/api/v1/dsp"

#: The SDK's own transport: every discovery request goes through it.
_DO_POST = "tractusx_sdk.dataspace.tools.http_tools.HttpTools.do_post"
_OAUTH = "tractusx_testlab.steps.discovery._lookup.OAuth2Manager"

_FINDER_ANSWER = {
    "endpoints": [
        {"type": "manufacturerPartId", "endpointAddress": "https://bpn-discovery.example"},
        {"type": "bpn", "endpointAddress": _EDC_DISCOVERY, "resourceId": "edc"},
    ]
}
_DISCOVERY_ANSWER = [
    {"bpn": "BPNL000000000002", "connectorEndpoint": ["https://other.example/api/v1/dsp"]},
    {"bpn": _BPNL, "connectorEndpoint": [_DSP, "https://second.example/api/v1/dsp", _DSP]},
]


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
    return StepDefinition(id="find", uses=_STEP)


def _urls(post: MagicMock) -> list[str]:
    return [call.kwargs["url"] for call in post.call_args_list]


class TestRegistration:
    def test_registered_for_every_release(self) -> None:
        assert StepRegistry.get(_STEP, "saturn") is not None
        assert StepRegistry.get(_STEP, "jupiter") is not None


class TestLookup:
    @pytest.mark.asyncio
    async def test_finder_then_edc_discovery_through_the_sdk(self) -> None:
        with patch(_DO_POST) as post:
            post.side_effect = [_answer(_FINDER_ANSWER), _answer(_DISCOVERY_ANSWER)]
            out = await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL}, _context(finder_url=_FINDER), _definition()
            )

        assert _urls(post) == [_FINDER, _EDC_DISCOVERY]
        assert post.call_args_list[0].kwargs["json"] == {"types": ["bpn"]}
        assert post.call_args_list[1].kwargs["json"] == [_BPNL]
        # Only this BPN's endpoints, once each, in the order the service gave them.
        assert out.value["connector_endpoints"] == [_DSP, "https://second.example/api/v1/dsp"]
        assert out.value["counter_party_address"] == _DSP
        assert out.value["edc_discovery_url"] == _EDC_DISCOVERY

    @pytest.mark.asyncio
    async def test_step_finder_url_wins_over_the_binding(self) -> None:
        other = "https://mock.example/run-1/api/v1.0/administration/connectors/discovery/search"
        with patch(_DO_POST) as post:
            post.side_effect = [_answer(_FINDER_ANSWER), _answer(_DISCOVERY_ANSWER)]
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL, "discovery_finder_url": other},
                _context(finder_url=_FINDER),
                _definition(),
            )
        assert _urls(post)[0] == other

    @pytest.mark.asyncio
    async def test_no_token_is_asked_for_without_an_idp(self) -> None:
        with patch(_DO_POST) as post, patch(_OAUTH) as oauth:
            post.side_effect = [_answer(_FINDER_ANSWER), _answer(_DISCOVERY_ANSWER)]
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL}, _context(finder_url=_FINDER), _definition()
            )
        oauth.assert_not_called()
        assert "Authorization" not in post.call_args_list[0].kwargs["headers"]


class TestTechnicalUser:
    @pytest.mark.asyncio
    async def test_the_bindings_user_signs_every_request(self) -> None:
        with patch(_DO_POST) as post, patch(_OAUTH) as oauth:
            oauth.return_value.connected = True
            oauth.return_value.add_auth_header.side_effect = lambda headers: {
                **headers,
                "Authorization": "Bearer tok-123",
            }
            post.side_effect = [_answer(_FINDER_ANSWER), _answer(_DISCOVERY_ANSWER)]
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL},
                _context(
                    finder_url=_FINDER,
                    oauth2_auth_url="https://centralidp.example/auth/",
                    oauth2_realm="CX-Central",
                    oauth2_client_id="engine",
                    oauth2_client_secret="s3cret",
                ),
                _definition(),
            )

        oauth.assert_called_once_with(
            auth_url="https://centralidp.example/auth/",
            realm="CX-Central",
            clientid="engine",
            clientsecret="s3cret",
        )
        for call in post.call_args_list:
            assert call.kwargs["headers"]["Authorization"] == "Bearer tok-123"
        assert "s3cret" not in mask("secret=s3cret")

    @pytest.mark.asyncio
    async def test_an_idp_that_will_not_sign_in_is_the_infrastructures_fault(self) -> None:
        with patch(_OAUTH, side_effect=ConnectionError("Unable to access the Keycloak instance")):
            with pytest.raises(BoundServiceError, match="identity provider"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL},
                    _context(
                        finder_url=_FINDER,
                        oauth2_auth_url="https://centralidp.example/auth/",
                        oauth2_realm="CX-Central",
                        oauth2_client_id="engine",
                    ),
                    _definition(),
                )

    @pytest.mark.asyncio
    async def test_auth_url_without_realm_or_client_is_refused(self) -> None:
        with pytest.raises(StepExecutionError, match="oauth2_realm or"):
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL},
                _context(finder_url=_FINDER, oauth2_auth_url="https://centralidp.example/auth/"),
                _definition(),
            )


class TestFailures:
    @pytest.mark.asyncio
    async def test_nothing_to_ask(self) -> None:
        with pytest.raises(StepExecutionError, match="no Discovery Finder to ask"):
            await ConnectorsByBpnStep().invoke({"bpnl": _BPNL}, _context(), _definition())

    @pytest.mark.asyncio
    async def test_finder_without_a_bpn_service_is_the_infrastructures_fault(self) -> None:
        with patch(_DO_POST) as post:
            post.return_value = _answer({"endpoints": []})
            with pytest.raises(BoundServiceError, match="EDC Discovery behind the Discovery"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL}, _context(finder_url=_FINDER), _definition()
                )

    @pytest.mark.asyncio
    async def test_unknown_bpn_fails_naming_the_service(self) -> None:
        with patch(_DO_POST) as post:
            post.side_effect = [_answer(_FINDER_ANSWER), _answer([])]
            with pytest.raises(StepExecutionError, match=f"{_EDC_DISCOVERY} holds no connector"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL}, _context(finder_url=_FINDER), _definition()
                )

    @pytest.mark.asyncio
    async def test_refusal_is_the_infrastructures_fault(self) -> None:
        with patch(_DO_POST) as post:
            post.side_effect = [_answer(_FINDER_ANSWER), _answer({"error": "forbidden"}, 403)]
            with pytest.raises(BoundServiceError, match="did not answer"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL}, _context(finder_url=_FINDER), _definition()
                )

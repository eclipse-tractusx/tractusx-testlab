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

"""Tests for discovery/connectors_by_bpn — the Discovery Finder → EDC Discovery lookup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import http_response
from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.logging.masking import forget_secrets, mask
from tractusx_testlab.models import StepDefinition, StepExecutionError
from tractusx_testlab.models.domain.discovery_capability import DiscoveryBinding
from tractusx_testlab.models.domain.infrastructure import EngineBindings, Infrastructure
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.discovery.connectors import ConnectorsByBpnStep

_STEP = "discovery/connectors_by_bpn"
_BPNL = "BPNL000000000001"
_FINDER = "https://finder.example/api/v1.0/administration/connectors/discovery/search"
_EDC_DISCOVERY = "https://edc-discovery.example/api/v1.0/administration/connectors/discovery"
_TOKEN_URL = "https://idp.example/realms/CX-Central/protocol/openid-connect/token"
_DSP = "https://provider.example/api/v1/dsp"

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


def _context(**binding: str) -> StepContext:
    config = MagicMock()
    config.default_timeout_s = 30
    job = MagicMock()
    job.job_id = "run-1"
    return StepContext(
        services=MagicMock(),
        job=job,
        config=config,
        infrastructure=Infrastructure(engine=EngineBindings(discovery=DiscoveryBinding(**binding))),
    )


def _definition() -> StepDefinition:
    return StepDefinition(id="find", uses=_STEP)


def _calls(post: AsyncMock) -> list[tuple[str, str]]:
    return [(call.args[0], call.args[1]) for call in post.await_args_list]


class TestRegistration:
    def test_registered_for_every_release(self) -> None:
        assert StepRegistry.get(_STEP, "saturn") is not None
        assert StepRegistry.get(_STEP, "jupiter") is not None


class TestLookup:
    @pytest.mark.asyncio
    async def test_finder_then_edc_discovery(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.side_effect = [http_response(_FINDER_ANSWER), http_response(_DISCOVERY_ANSWER)]
            out = await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL}, _context(finder_url=_FINDER), _definition()
            )

        assert _calls(post) == [("POST", _FINDER), ("POST", _EDC_DISCOVERY)]
        assert post.await_args_list[0].kwargs["json"] == {"types": ["bpn"]}
        assert post.await_args_list[1].kwargs["json"] == [_BPNL]
        value = out.value
        # Only this BPN's endpoints, once each, in the order the service gave them.
        assert value["connector_endpoints"] == [_DSP, "https://second.example/api/v1/dsp"]
        assert value["counter_party_address"] == _DSP
        assert value["edc_discovery_url"] == _EDC_DISCOVERY
        assert value["discovery"] == _DISCOVERY_ANSWER
        assert out.request.url == _EDC_DISCOVERY

    @pytest.mark.asyncio
    async def test_edc_discovery_url_skips_the_finder(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = http_response(_DISCOVERY_ANSWER)
            out = await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL, "edc_discovery_url": _EDC_DISCOVERY}, _context(), _definition()
            )
        assert _calls(post) == [("POST", _EDC_DISCOVERY)]
        assert out.value["counter_party_address"] == _DSP

    @pytest.mark.asyncio
    async def test_step_finder_url_wins_over_the_binding(self) -> None:
        other = "https://mock.example/run-1/api/v1.0/administration/connectors/discovery/search"
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.side_effect = [http_response(_FINDER_ANSWER), http_response(_DISCOVERY_ANSWER)]
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL, "discovery_finder_url": other},
                _context(finder_url=_FINDER),
                _definition(),
            )
        assert _calls(post)[0] == ("POST", other)

    @pytest.mark.asyncio
    async def test_bpn_is_matched_without_regard_to_case(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = http_response([{"bpn": _BPNL.lower(), "connectorEndpoint": _DSP}])
            out = await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL, "edc_discovery_url": _EDC_DISCOVERY}, _context(), _definition()
            )
        assert out.value["connector_endpoints"] == [_DSP]


class TestAuthentication:
    @pytest.mark.asyncio
    async def test_client_credentials_token_is_sent_and_masked(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.side_effect = [
                http_response({"access_token": "tok-123", "token_type": "Bearer"}),
                http_response(_FINDER_ANSWER),
                http_response(_DISCOVERY_ANSWER),
            ]
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL},
                _context(
                    finder_url=_FINDER,
                    token_url=_TOKEN_URL,
                    client_id="engine",
                    client_secret="s3cret",
                    scope="openid",
                ),
                _definition(),
            )

        token_call, finder_call, discovery_call = post.await_args_list
        assert token_call.args == ("POST", _TOKEN_URL)
        assert token_call.kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "engine",
            "client_secret": "s3cret",
            "scope": "openid",
        }
        for call in (finder_call, discovery_call):
            assert call.kwargs["headers"]["Authorization"] == "Bearer tok-123"
            assert "Authorization" in call.kwargs["secret_headers"]
        assert "tok-123" not in mask("Bearer tok-123")
        assert "s3cret" not in mask("secret=s3cret")

    @pytest.mark.asyncio
    async def test_given_access_token_replaces_client_credentials(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = http_response(_DISCOVERY_ANSWER)
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL, "edc_discovery_url": _EDC_DISCOVERY, "access_token": "given"},
                _context(token_url=_TOKEN_URL, client_id="engine", client_secret="x"),
                _definition(),
            )
        assert _calls(post) == [("POST", _EDC_DISCOVERY)]
        assert post.await_args.kwargs["headers"]["Authorization"] == "Bearer given"

    @pytest.mark.asyncio
    async def test_refused_token_names_the_client(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = http_response({"error": "unauthorized_client"}, status=401)
            with pytest.raises(StepExecutionError, match="'engine' no token"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL},
                    _context(
                        finder_url=_FINDER,
                        token_url=_TOKEN_URL,
                        client_id="engine",
                        client_secret="bad",
                    ),
                    _definition(),
                )

    @pytest.mark.asyncio
    async def test_token_url_without_client_id_is_refused(self) -> None:
        with pytest.raises(StepExecutionError, match="client_id is not"):
            await ConnectorsByBpnStep().invoke(
                {"bpnl": _BPNL}, _context(finder_url=_FINDER, token_url=_TOKEN_URL), _definition()
            )


class TestFailures:
    @pytest.mark.asyncio
    async def test_nothing_to_ask(self) -> None:
        with pytest.raises(StepExecutionError, match="no Discovery Finder to ask"):
            await ConnectorsByBpnStep().invoke({"bpnl": _BPNL}, _context(), _definition())

    @pytest.mark.asyncio
    async def test_finder_without_a_bpn_service(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = http_response({"endpoints": []})
            with pytest.raises(StepExecutionError, match="no discovery service of type 'bpn'"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL}, _context(finder_url=_FINDER), _definition()
                )

    @pytest.mark.asyncio
    async def test_unknown_bpn_fails_naming_the_service(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = http_response([])
            with pytest.raises(StepExecutionError, match="holds no connector endpoint"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL, "edc_discovery_url": _EDC_DISCOVERY},
                    _context(),
                    _definition(),
                )

    @pytest.mark.asyncio
    async def test_refusal_quotes_the_status(self) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = http_response({"error": "forbidden"}, status=403)
            with pytest.raises(StepExecutionError, match="HTTP 403"):
                await ConnectorsByBpnStep().invoke(
                    {"bpnl": _BPNL, "edc_discovery_url": _EDC_DISCOVERY},
                    _context(),
                    _definition(),
                )

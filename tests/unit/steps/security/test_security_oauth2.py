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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""Tests for the security/oauth2/* steps — obtaining OAuth2 authorization tokens."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import http_response
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps.security.oauth2 import (
    OAuth2ClientCredentialsStep,
    OAuth2PasswordStep,
    OAuth2RefreshTokenStep,
)

_TOKEN_URL = "https://idp.example/realms/CX/protocol/openid-connect/token"

# A realistic Keycloak answer: the RFC fields plus vendor extras that must
# round-trip untouched.
_TOKEN_RESPONSE = {
    "access_token": "eyJhbGciOi...",
    "token_type": "Bearer",
    "expires_in": 300,
    "scope": "openid",
    "refresh_expires_in": 1800,
}


@pytest.fixture()
def context() -> StepContext:
    config = MagicMock()
    config.default_timeout_s = 30
    return StepContext(services=MagicMock(), job=MagicMock(), config=config)


def _definition(uses: str = "security/oauth2/client_credentials") -> StepDefinition:
    return StepDefinition(id="token", uses=uses)


def _response(status_code: int = 200, body: dict | None = None) -> MagicMock:
    """The token endpoint's answer, shaped like the httpx.Response the step gets.

    Built through the shared helper because a step reads a response via
    ``steps.http_client``, which inspects the content type before parsing and
    the raw header pairs to keep the server's casing. A plain dict of headers
    silently fails the first of those: ``{"Content-Type": ...}.get("content-type")``
    is ``None``, so the body comes back as text.
    """
    return http_response(
        _TOKEN_RESPONSE if body is None else body,
        status=status_code,
    )


class TestRegistration:
    """One step per grant; the old mixed step name is gone."""

    @pytest.mark.parametrize(
        "step_type",
        [
            "security/oauth2/client_credentials",
            "security/oauth2/password",
            "security/oauth2/refresh_token",
        ],
    )
    def test_each_grant_is_its_own_step(self, step_type: str) -> None:
        assert StepRegistry.get(step_type, "") is not None

    def test_the_mixed_get_token_step_is_gone(self) -> None:
        assert StepRegistry.get("security/oauth2/get_token", "") is None

    @pytest.mark.asyncio
    async def test_a_step_cannot_be_asked_for_another_grant(self, context: StepContext) -> None:
        """The grant is the step name; ``grant_type`` is not even an input key."""
        with pytest.raises(ValueError, match="grant_type"):
            await OAuth2ClientCredentialsStep().invoke(
                {"token_url": _TOKEN_URL, "grant_type": "password"},
                context,
                _definition(),
            )


class TestOAuth2ClientCredentialsStep:
    @pytest.mark.asyncio
    async def test_client_credentials_returns_the_token_response(
        self, context: StepContext
    ) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response()
            output = await OAuth2ClientCredentialsStep().invoke(
                {
                    "token_url": _TOKEN_URL,
                    "client_id": "testlab",
                    "client_secret": "s3cret",
                    "scope": "openid",
                },
                context,
                _definition(),
            )

        assert output.value == _TOKEN_RESPONSE
        assert post.call_args.kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "testlab",
            "client_secret": "s3cret",
            "scope": "openid",
        }
        assert post.call_args.kwargs["auth"] is None

    @pytest.mark.asyncio
    async def test_publishes_the_access_token_for_later_steps(self, context: StepContext) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response()
            await OAuth2ClientCredentialsStep().invoke(
                {"token_url": _TOKEN_URL, "client_id": "testlab"},
                context,
                _definition(),
            )
        assert context.get_variable("access_token") == "eyJhbGciOi..."
        assert context.get_variable("expires_in") == 300

    @pytest.mark.asyncio
    async def test_basic_auth_keeps_credentials_out_of_the_form(self, context: StepContext) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response()
            await OAuth2ClientCredentialsStep().invoke(
                {
                    "token_url": _TOKEN_URL,
                    "client_id": "testlab",
                    "client_secret": "s3cret",
                    "client_auth": "basic",
                },
                context,
                _definition(),
            )
        assert post.call_args.kwargs["auth"] == ("testlab", "s3cret")
        assert "client_secret" not in post.call_args.kwargs["data"]

    @pytest.mark.asyncio
    async def test_a_missing_token_url_fails_before_the_request(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="token_url: Field required"):
            await OAuth2ClientCredentialsStep().invoke({}, context, _definition())

    @pytest.mark.asyncio
    async def test_a_refusal_returns_no_value_but_records_the_response(
        self, context: StepContext
    ) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response(401, {"error": "invalid_client"})
            output = await OAuth2ClientCredentialsStep().invoke(
                {"token_url": _TOKEN_URL, "client_id": "testlab", "client_secret": "wrong"},
                context,
                _definition(),
            )
        assert output.value is None
        assert output.response.status_code == 401
        assert output.response.body == {"error": "invalid_client"}

    @pytest.mark.asyncio
    async def test_secrets_are_redacted_from_the_recorded_request(
        self, context: StepContext
    ) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response()
            output = await OAuth2ClientCredentialsStep().invoke(
                {
                    "token_url": _TOKEN_URL,
                    "client_id": "testlab",
                    "client_secret": "s3cret",
                },
                context,
                _definition(),
            )
        assert output.request.body["client_secret"] == "***"
        assert output.request.body["client_id"] == "testlab"
        # The real secret still went over the wire.
        assert post.call_args.kwargs["data"]["client_secret"] == "s3cret"

    @pytest.mark.asyncio
    async def test_extra_fields_are_merged_into_the_form(self, context: StepContext) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response()
            await OAuth2ClientCredentialsStep().invoke(
                {
                    "token_url": _TOKEN_URL,
                    "client_id": "testlab",
                    "extra_fields": {"audience": "https://api.example"},
                },
                context,
                _definition(),
            )
        assert post.call_args.kwargs["data"]["audience"] == "https://api.example"


class TestOAuth2PasswordStep:
    @pytest.mark.asyncio
    async def test_password_grant_sends_owner_credentials(self, context: StepContext) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response()
            await OAuth2PasswordStep().invoke(
                {
                    "token_url": _TOKEN_URL,
                    "client_id": "testlab",
                    "username": "alice",
                    "password": "wonderland",
                },
                context,
                _definition("security/oauth2/password"),
            )
        form = post.call_args.kwargs["data"]
        assert form["grant_type"] == "password"
        assert form["username"] == "alice"
        assert form["password"] == "wonderland"

    @pytest.mark.asyncio
    async def test_password_grant_without_credentials_fails_validation(
        self, context: StepContext
    ) -> None:
        with pytest.raises(ValueError, match="username"):
            await OAuth2PasswordStep().invoke(
                {"token_url": _TOKEN_URL},
                context,
                _definition("security/oauth2/password"),
            )


class TestOAuth2RefreshTokenStep:
    @pytest.mark.asyncio
    async def test_refresh_grant_exchanges_the_refresh_token(self, context: StepContext) -> None:
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as post:
            post.return_value = _response()
            await OAuth2RefreshTokenStep().invoke(
                {
                    "token_url": _TOKEN_URL,
                    "client_id": "testlab",
                    "refresh_token": "the-old-one",
                },
                context,
                _definition("security/oauth2/refresh_token"),
            )
        form = post.call_args.kwargs["data"]
        assert form["grant_type"] == "refresh_token"
        assert form["refresh_token"] == "the-old-one"

    @pytest.mark.asyncio
    async def test_refresh_grant_requires_the_refresh_token(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="refresh_token"):
            await OAuth2RefreshTokenStep().invoke(
                {"token_url": _TOKEN_URL},
                context,
                _definition("security/oauth2/refresh_token"),
            )

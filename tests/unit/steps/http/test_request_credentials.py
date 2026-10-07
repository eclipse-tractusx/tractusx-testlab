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

"""``http/http_request`` releases a credential handle to its own origin, and nowhere else."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging import wire
from tractusx_testlab.models import Job, StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.security.credentials import (
    Credential,
    CredentialNotReleasedError,
    CredentialOriginMismatchError,
)
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.http.request import HttpRequestStep

_SECRET = "platform-management-key-0123"
_MANAGEMENT = "https://cp.example.com/management"


def _handle(side: str = "engine") -> Credential:
    return Credential(
        _SECRET,
        name=f"infrastructure.{side}.connector.api_key",
        side=side,
        origins=["https://cp.example.com:443"],
    )


def _context(released: set[str] | None = None) -> StepContext:
    config = TestlabConfig() if released is None else TestlabConfig(credential_release=released)
    return StepContext(services=ServiceManager(), job=Job(job_id="run-1"), config=config)


def _response(url: str) -> MagicMock:
    response = MagicMock(status_code=200, url=url)
    response.headers = MagicMock(
        raw=[(b"content-type", b"application/json")],
        **{"get.side_effect": {"content-type": "application/json"}.get},
    )
    response.json.return_value = {"ok": True}
    return response


async def _send(url: str, context: StepContext, side: str = "engine") -> tuple[Any, AsyncMock]:
    with patch(
        "tractusx_testlab.steps.http_client.request",
        new_callable=AsyncMock,
        return_value=_response(url),
    ) as request:
        output = await HttpRequestStep().invoke(
            {"url": url, "headers": {"x-api-key": _handle(side), "Accept": "application/json"}},
            context,
            StepDefinition(id="s", uses="http/http_request"),
        )
    return output, request


class TestRelease:
    @pytest.mark.asyncio
    async def test_the_key_goes_on_the_wire_to_its_own_origin(self) -> None:
        output, request = await _send(f"{_MANAGEMENT}/v3/assets", _context())

        sent = request.call_args.kwargs
        assert sent["headers"] == {"x-api-key": _SECRET, "Accept": "application/json"}
        assert sent["secret_headers"] == frozenset({"x-api-key"})
        # A redirect would carry the key somewhere nobody checked.
        assert sent["follow_redirects"] is False
        assert output.request.headers["x-api-key"] == "***"

    @pytest.mark.asyncio
    async def test_a_request_without_a_credential_still_follows_redirects(self) -> None:
        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=_response("https://api.example.com"),
        ) as request:
            await HttpRequestStep().invoke(
                {"url": "https://api.example.com"},
                _context(),
                StepDefinition(id="s", uses="http/http_request"),
            )
        assert request.call_args.kwargs["follow_redirects"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url",
        [
            "https://cp.example.com.evil.io/management/v3/assets",
            "http://cp.example.com/management/v3/assets",
            "https://cp.example.com:8443/management/v3/assets",
            "https://evil.io/collect",
        ],
    )
    async def test_any_other_origin_fails_the_step_before_anything_is_sent(self, url: str) -> None:
        with pytest.raises(CredentialOriginMismatchError):
            await _send(url, _context())

    @pytest.mark.asyncio
    async def test_a_side_the_host_withholds_is_refused(self) -> None:
        with pytest.raises(CredentialNotReleasedError):
            await _send(f"{_MANAGEMENT}/v3/assets", _context({"sut"}))

    @pytest.mark.asyncio
    async def test_the_released_side_still_works(self) -> None:
        output, request = await _send(f"{_MANAGEMENT}/v3/assets", _context({"sut"}), side="sut")
        assert request.call_args.kwargs["headers"]["x-api-key"] == _SECRET
        assert output.request.headers["x-api-key"] == "***"


class TestRecord:
    @pytest.mark.asyncio
    async def test_a_credential_header_is_traced_as_the_marker_whatever_its_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[httpx.Request] = []

        def answer(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={})

        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            http_client.httpx,
            "AsyncClient",
            lambda **kwargs: real_client(transport=httpx.MockTransport(answer), **kwargs),
        )
        with wire.recording("step") as recorder:
            await http_client.request(
                "GET",
                f"{_MANAGEMENT}/v3/assets",
                headers={"X-Custom-Key": _SECRET},
                secret_headers={"X-Custom-Key"},
            )

        assert seen[0].headers["X-Custom-Key"] == _SECRET
        assert recorder.exchanges[0].request.headers["X-Custom-Key"] == "***"

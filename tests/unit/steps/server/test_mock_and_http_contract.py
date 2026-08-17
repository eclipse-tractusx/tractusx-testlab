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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Contract tests for the mock-server and plain-HTTP steps."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import (
    clear_mocks,
    get_mock,
    set_callback_manager,
)
from tractusx_testlab.steps.connector.utils import HttpRequestStep
from tractusx_testlab.steps.server.mock import MockEndpointStep
from tractusx_testlab.steps.server.wait import WaitForCallParams, WaitForCallStep

_PATH = "/companycertificate/notification/receive"


def _definition(uses: str) -> StepDefinition:
    return StepDefinition(id="s", uses=uses)


@pytest.fixture()
def context(mock_context: MagicMock) -> MagicMock:
    mock_context.config.server_port = 8080
    mock_context.config.default_timeout_s = 30
    return mock_context


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    clear_mocks()
    yield
    clear_mocks()


# ---------------------------------------------------------------------------
# C38 / C31 — what mock/api registers and returns
# ---------------------------------------------------------------------------


class TestMockEndpoint:
    @pytest.mark.asyncio
    async def test_it_returns_the_mock_and_both_urls(self, context: MagicMock) -> None:
        output = await MockEndpointStep().invoke(
            {"path": _PATH, "method": "POST"}, context, _definition("mock/api")
        )

        assert output.value["base_mock_url"] == "http://localhost:8080"
        assert output.value["full_mock_url"] == f"http://localhost:8080{_PATH}"
        assert output.value["mock"]["path"] == _PATH
        assert output.value["mock"]["method"] == "POST"

    @pytest.mark.asyncio
    async def test_the_mock_carries_the_id_it_was_registered_under(
        self, context: MagicMock
    ) -> None:
        output = await MockEndpointStep().invoke(
            {"id": "ack", "path": _PATH}, context, _definition("mock/api")
        )
        assert output.value["mock"]["endpoint_id"] == "ack"

    @pytest.mark.asyncio
    async def test_response_headers_are_part_of_the_canned_reply(
        self, context: MagicMock
    ) -> None:
        """C31 — a mock standing in for a real API has to answer like one."""
        await MockEndpointStep().invoke(
            {
                "path": _PATH,
                "method": "POST",
                "response_headers": {"content-type": "application/json"},
            },
            context,
            _definition("mock/api"),
        )
        assert get_mock(_PATH, "POST").headers == {"content-type": "application/json"}

    @pytest.mark.asyncio
    async def test_a_mock_with_no_headers_answers_with_none(
        self, context: MagicMock
    ) -> None:
        await MockEndpointStep().invoke(
            {"path": _PATH}, context, _definition("mock/api")
        )
        assert get_mock(_PATH, "POST").headers == {}

    @pytest.mark.asyncio
    async def test_a_path_without_its_leading_slash_still_matches(
        self, context: MagicMock
    ) -> None:
        output = await MockEndpointStep().invoke(
            {"path": "callback"}, context, _definition("mock/api")
        )
        assert output.value["mock"]["path"] == "/callback"


# ---------------------------------------------------------------------------
# C17 / C39 — what mock/wait/http_request takes and hands back
# ---------------------------------------------------------------------------


class TestWaitForCall:
    def test_it_takes_a_mock_and_not_a_url(self) -> None:
        """C17 — the mock knows its own path and method; nothing to re-derive."""
        with pytest.raises(ValueError):
            WaitForCallParams.model_validate({"mock": "http://localhost:8080/callback"})

    def test_it_takes_a_mock_and_not_an_id(self) -> None:
        with pytest.raises(ValueError):
            WaitForCallParams.model_validate({"mock": "ack"})

    @pytest.mark.asyncio
    async def test_it_waits_on_the_mock_it_was_given(self, context: MagicMock) -> None:
        manager = CallbackManager()
        set_callback_manager(manager)
        registered = await MockEndpointStep().invoke(
            {"path": _PATH, "method": "POST"}, context, _definition("mock/api")
        )
        manager.resolve(
            _PATH, "POST", {"x-trace": "1"}, {"status": "RECEIVED"}, {"page": "2"}
        )

        output = await WaitForCallStep().invoke(
            {"mock": registered.value["mock"], "timeout_s": 1},
            context,
            _definition("mock/wait/http_request"),
        )

        assert output.value["request_method"] == "POST"
        assert output.value["request_path"] == _PATH
        assert output.value["request_headers"] == {"x-trace": "1"}
        assert output.value["request_body"] == {"status": "RECEIVED"}

    @pytest.mark.asyncio
    async def test_the_query_string_the_sut_sent_is_readable(
        self, context: MagicMock
    ) -> None:
        """C39 — a callback's query parameters are part of what arrived."""
        manager = CallbackManager()
        set_callback_manager(manager)
        registered = await MockEndpointStep().invoke(
            {"path": _PATH}, context, _definition("mock/api")
        )
        manager.resolve(_PATH, "POST", {}, None, {"notificationId": "n-1"})

        output = await WaitForCallStep().invoke(
            {"mock": registered.value["mock"], "timeout_s": 1},
            context,
            _definition("mock/wait/http_request"),
        )

        assert output.value["request_query_params"] == {"notificationId": "n-1"}

    @pytest.mark.asyncio
    async def test_how_long_the_wait_took_is_reported(self, context: MagicMock) -> None:
        manager = CallbackManager()
        set_callback_manager(manager)
        registered = await MockEndpointStep().invoke(
            {"path": _PATH}, context, _definition("mock/api")
        )
        manager.resolve(_PATH, "POST", {}, None)

        output = await WaitForCallStep().invoke(
            {"mock": registered.value["mock"], "timeout_s": 1},
            context,
            _definition("mock/wait/http_request"),
        )

        assert output.value["elapsed_ms"] >= 0

    @pytest.mark.asyncio
    async def test_a_call_that_never_arrives_fails_the_step(
        self, context: MagicMock
    ) -> None:
        set_callback_manager(CallbackManager())
        registered = await MockEndpointStep().invoke(
            {"path": _PATH}, context, _definition("mock/api")
        )

        with pytest.raises(RuntimeError, match="Timed out"):
            await WaitForCallStep().invoke(
                {"mock": registered.value["mock"], "timeout_s": 0.01},
                context,
                _definition("mock/wait/http_request"),
            )


# ---------------------------------------------------------------------------
# C30 — query parameters on the plain HTTP step
# ---------------------------------------------------------------------------


class TestHttpRequestQueryParams:
    @pytest.mark.asyncio
    async def test_they_reach_the_request(self, context: MagicMock) -> None:
        response = MagicMock(status_code=200, headers={}, url="https://api.example.com?a=1")
        response.json.return_value = {"ok": True}

        with patch(
            "tractusx_testlab.steps.connector.utils.requests.request", return_value=response
        ) as request:
            await HttpRequestStep().invoke(
                {"url": "https://api.example.com", "query_params": {"a": "1"}},
                context,
                _definition("http/http_request"),
            )

        assert request.call_args.kwargs["params"] == {"a": "1"}

    @pytest.mark.asyncio
    async def test_no_query_params_sends_none_rather_than_an_empty_mapping(
        self, context: MagicMock
    ) -> None:
        response = MagicMock(status_code=200, headers={}, url="https://api.example.com")
        response.json.return_value = {}

        with patch(
            "tractusx_testlab.steps.connector.utils.requests.request", return_value=response
        ) as request:
            await HttpRequestStep().invoke(
                {"url": "https://api.example.com"}, context, _definition("http/http_request")
            )

        assert request.call_args.kwargs["params"] is None

    @pytest.mark.asyncio
    async def test_the_reported_url_is_the_one_actually_called(
        self, context: MagicMock
    ) -> None:
        """A request logged without its query string cannot be replayed."""
        response = MagicMock(
            status_code=200, headers={}, url="https://api.example.com?a=1"
        )
        response.json.return_value = {}

        with patch(
            "tractusx_testlab.steps.connector.utils.requests.request", return_value=response
        ):
            output = await HttpRequestStep().invoke(
                {"url": "https://api.example.com", "query_params": {"a": "1"}},
                context,
                _definition("http/http_request"),
            )

        assert output.request.url == "https://api.example.com?a=1"

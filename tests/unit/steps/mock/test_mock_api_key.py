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

"""A mock behind a connector answers only calls the connector's data plane forwards.

``mock/api`` with ``require_api_key`` mints a key, the test puts it in the data
address of the asset that fronts the mock, and the mock refuses every call that
does not carry it. What is pinned here: the key is minted and returned, the
mock server enforces it on both of its routes without letting a refused call
stand in for the awaited one, and the key never reaches a record of the run.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging.masking import forget_secrets, mask
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.server.app import create_app
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import (
    MockResponse,
    admits,
    clear_callback_manager,
    clear_mocks,
    register_mock,
    set_callback_manager,
)
from tractusx_testlab.steps.mock.api import MockEndpointParams, MockEndpointStep
from tractusx_testlab.steps.mock.wait import WaitForCallStep

_PATH = "/uniqueidpush/connect-to-parent"


def _definition(uses: str) -> StepDefinition:
    return StepDefinition(id="s", uses=uses)


@pytest.fixture()
def context(mock_context: MagicMock) -> MagicMock:
    mock_context.config.server_port = 8080
    mock_context.config.mock_public_url = None
    return mock_context


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_mocks()
    forget_secrets()
    yield
    clear_mocks()
    forget_secrets()
    clear_callback_manager()


async def _register(context: MagicMock, **params: Any) -> dict[str, Any]:
    output = await MockEndpointStep().invoke(
        {"path": _PATH, "method": "POST", **params}, context, _definition("mock/api")
    )
    return output.value


class TestTheStep:
    @pytest.mark.asyncio
    async def test_a_plain_mock_requires_nothing(self, context: MagicMock) -> None:
        value = await _register(context)

        assert value["api_key"] == ""
        assert admits(_PATH, "POST", {})

    @pytest.mark.asyncio
    async def test_require_api_key_mints_a_key_and_returns_it(self, context: MagicMock) -> None:
        value = await _register(context, require_api_key=True)

        assert len(value["api_key"]) >= 32
        assert not admits(_PATH, "POST", {})
        assert admits(_PATH, "POST", {"x-api-key": value["api_key"]})

    @pytest.mark.asyncio
    async def test_every_registration_mints_a_new_key(self, context: MagicMock) -> None:
        first = await _register(context, require_api_key=True)
        second = await _register(context, require_api_key=True)

        assert first["api_key"] != second["api_key"]
        assert not admits(_PATH, "POST", {"x-api-key": first["api_key"]})

    @pytest.mark.asyncio
    async def test_a_given_key_is_required_as_given(self, context: MagicMock) -> None:
        """Two mocks behind one asset share the key the asset carries."""
        shared = "shared-key-from-the-first-mock"
        value = await _register(context, api_key=shared, api_key_header="X-Mock-Key")

        assert value["api_key"] == shared
        assert admits(_PATH, "POST", {"x-mock-key": shared})
        assert not admits(_PATH, "POST", {"x-api-key": shared})

    @pytest.mark.asyncio
    async def test_the_key_is_masked_from_the_moment_it_is_minted(self, context: MagicMock) -> None:
        value = await _register(context, require_api_key=True)

        assert mask({"api_key": value["api_key"]}) == {"api_key": "***"}

    @pytest.mark.asyncio
    async def test_registering_the_path_again_without_a_key_opens_it(
        self, context: MagicMock
    ) -> None:
        await _register(context, require_api_key=True)
        await _register(context)

        assert admits(_PATH, "POST", {})

    def test_a_key_too_short_to_mask_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="at least"):
            MockEndpointParams(path=_PATH, api_key="short")


class TestTheRegistry:
    def test_the_header_name_is_matched_without_regard_to_case(self) -> None:
        register_mock(
            _PATH, "POST", MockResponse(status_code=200), required_header=("X-Api-Key", "k" * 16)
        )
        assert admits(_PATH, "POST", {"X-API-KEY": "k" * 16})

    def test_a_wrong_value_is_refused(self) -> None:
        register_mock(
            _PATH, "POST", MockResponse(status_code=200), required_header=("x-api-key", "k" * 16)
        )
        assert not admits(_PATH, "POST", {"x-api-key": "j" * 16})

    def test_the_guard_is_per_method(self) -> None:
        register_mock(
            _PATH, "POST", MockResponse(status_code=200), required_header=("x-api-key", "k" * 16)
        )
        assert admits(_PATH, "GET", {})


class TestTheServer:
    @pytest.fixture()
    def client(self, tmp_path: Path) -> Iterator[TestClient]:
        manager = CallbackManager()
        set_callback_manager(manager)
        app = create_app(config=TestlabConfig(storage_dir=tmp_path, logs_dir=tmp_path))
        with TestClient(app) as client:
            yield client

    @pytest.fixture()
    def key(self, client: TestClient) -> str:
        # Registered as mock/api registers it, without the listener it opens:
        # that belongs to the step's event loop, and here there is none.
        key = "k" * 32
        register_mock(
            _PATH, "POST", MockResponse(status_code=200), required_header=("x-api-key", key)
        )
        return key

    def test_a_call_without_the_key_is_refused_and_counted(
        self, client: TestClient, key: str
    ) -> None:
        answer = client.post(_PATH, json={"a": 1})

        assert answer.status_code == 401
        assert "through the connector" in answer.json()["detail"]
        assert key not in answer.text
        manager = client.app.state.callbacks
        assert manager.refused(_PATH, "POST") == 1

    def test_a_refused_call_does_not_stand_in_for_the_awaited_one(
        self, client: TestClient, key: str
    ) -> None:
        client.post(_PATH, json={"a": 1})

        manager: CallbackManager = client.app.state.callbacks
        assert manager._buffered == {}
        future = manager._listeners.get(f"POST:{_PATH}")
        assert future is None or not future.done()

    def test_a_call_with_the_key_is_answered(self, client: TestClient, key: str) -> None:
        answer = client.post(_PATH, json={"a": 1}, headers={"X-Api-Key": key})

        assert answer.status_code == 200

    def test_the_callbacks_route_enforces_the_key_too(self, client: TestClient) -> None:
        path, key = "/callbacks/ccm/status", "k" * 32
        register_mock(
            path, "POST", MockResponse(status_code=200), required_header=("x-api-key", key)
        )

        assert client.post(path, json={}).status_code == 401
        assert client.post(path, json={}, headers={"x-api-key": key}).status_code == 200


class TestTheWait:
    @pytest.mark.asyncio
    async def test_a_timeout_says_calls_were_refused(self, context: MagicMock) -> None:
        manager = CallbackManager()
        set_callback_manager(manager)
        registered = await _register(context, require_api_key=True)
        manager.refuse(_PATH, "POST")
        manager.refuse(_PATH, "POST")

        with pytest.raises(RuntimeError, match=r"2 call\(s\) reached the mock without the key"):
            await WaitForCallStep().invoke(
                {"mock": registered["mock"], "timeout_s": 0.01},
                context,
                _definition("mock/wait/http_request"),
            )

    @pytest.mark.asyncio
    async def test_a_timeout_with_nothing_refused_says_only_that(self, context: MagicMock) -> None:
        set_callback_manager(CallbackManager())
        registered = await _register(context, require_api_key=True)

        with pytest.raises(RuntimeError) as raised:
            await WaitForCallStep().invoke(
                {"mock": registered["mock"], "timeout_s": 0.01},
                context,
                _definition("mock/wait/http_request"),
            )
        assert "refused" not in str(raised.value)

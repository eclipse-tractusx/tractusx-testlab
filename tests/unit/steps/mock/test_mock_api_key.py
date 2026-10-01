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

"""Every mock requires the run's API key, and a reflexive asset carries it.

``mock/api`` registers every mock behind the key of the run it belongs to, and
refuses every call without it; ``public`` is the one way out. The key is hidden
in every record of the run unless the step's ``returns:`` says ``hidden:
false``. ``connector/provider/create_mock_asset`` offers the mock on the engine
connector with the key in the asset's data address, read from the mock, so the
test never names it.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging.masking import forget_secrets, mask
from tractusx_testlab.models import AuthoringError, StepDefinition
from tractusx_testlab.models.authoring.definitions import ReturnFieldDefinition
from tractusx_testlab.player.execution._step_outputs import hide_secrets
from tractusx_testlab.server.app import create_app
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.inbound.run_scope import scoped
from tractusx_testlab.server.mock_registry import (
    MISSING_KEY,
    WRONG_KEY,
    MockResponse,
    _mint_key,
    admits,
    clear_callback_manager,
    clear_mocks,
    register_mock,
    required_header,
    run_key,
    set_callback_manager,
)
from tractusx_testlab.steps.connector.provision.mock_asset import (
    CreateMockAssetParams,
    CreateMockAssetStep,
)
from tractusx_testlab.steps.mock.api import MockEndpointStep
from tractusx_testlab.steps.mock.wait import (
    MockCallRefusedError,
    WaitForCallStep,
    WaitForDataplaneCallStep,
)
from tractusx_testlab.steps.step_contract import StepOutput

_PATH = "/uniqueidpush/connect-to-parent"
#: Where run-1's mock and listener on ``_PATH`` are kept.
_KEY = scoped("run-1", _PATH)


def _definition(uses: str, returns: dict[str, Any] | None = None) -> StepDefinition:
    return StepDefinition(id="s", uses=uses, returns=returns)


@pytest.fixture()
def context(mock_context: MagicMock) -> MagicMock:
    mock_context.config.server_port = 8080
    mock_context.config.mock_public_url = None
    mock_context.job.job_id = "run-1"
    return mock_context


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_mocks()
    forget_secrets()
    yield
    clear_mocks()
    forget_secrets()
    clear_callback_manager()


async def _register(context: MagicMock, path: str = _PATH, **params: Any) -> dict[str, Any]:
    output = await MockEndpointStep().invoke(
        {"path": path, "method": "POST", **params}, context, _definition("mock/api")
    )
    return output.value


class TestEveryMockRequiresTheKey:
    @pytest.mark.asyncio
    async def test_a_mock_refuses_a_call_without_the_key(self, context: MagicMock) -> None:
        value = await _register(context)

        assert len(value["api_key"]) >= 32
        assert not admits(_PATH, "POST", {})
        assert admits(_PATH, "POST", {"x-api-key": value["api_key"]})

    @pytest.mark.asyncio
    async def test_the_mocks_of_one_run_share_its_key(self, context: MagicMock) -> None:
        """One asset can front several mocks, and a re-armed mock keeps its key."""
        push = await _register(context, "/companycertificate/push")
        status = await _register(context, "/companycertificate/status")
        rearmed = await _register(context, "/companycertificate/status")

        assert push["api_key"] == status["api_key"] == rearmed["api_key"]

    def test_the_key_is_a_256_bit_blake2b_digest_minted_once_per_run(self) -> None:
        first = run_key("run-digest")

        assert re.fullmatch(r"[0-9a-f]{64}", first)
        assert run_key("run-digest") == first
        assert run_key("run-digest-other") != first

    def test_two_mintings_for_the_same_run_id_differ(self) -> None:
        """The nonce, not the run id, is what makes a key unguessable."""
        first, second = (_mint_key("same-run") for _ in range(2))

        assert first != second

    @pytest.mark.asyncio
    async def test_a_wrong_key_is_refused(self, context: MagicMock) -> None:
        await _register(context)

        assert not admits(_PATH, "POST", {"X-API-KEY": "j" * 43})

    @pytest.mark.asyncio
    async def test_another_run_has_another_key(self, context: MagicMock) -> None:
        """Each run keeps its own mock on the path, and only its own key opens it."""
        first = await _register(context)
        context.job.job_id = "run-2"
        second = await _register(context)

        assert first["api_key"] != second["api_key"]
        assert not admits(scoped("run-2", _PATH), "POST", {"x-api-key": first["api_key"]})
        assert admits(scoped("run-1", _PATH), "POST", {"x-api-key": first["api_key"]})

    @pytest.mark.asyncio
    async def test_the_header_can_be_named(self, context: MagicMock) -> None:
        value = await _register(context, api_key_header="X-Mock-Key")

        assert admits(_PATH, "POST", {"x-mock-key": value["api_key"]})
        assert not admits(_PATH, "POST", {"x-api-key": value["api_key"]})

    @pytest.mark.asyncio
    async def test_a_public_mock_answers_anyone(self, context: MagicMock) -> None:
        value = await _register(context, public=True)

        assert value["api_key"] == ""
        assert admits(_PATH, "POST", {})

    @pytest.mark.asyncio
    async def test_registering_the_path_again_as_public_opens_it(self, context: MagicMock) -> None:
        await _register(context)
        await _register(context, public=True)

        assert admits(_PATH, "POST", {})


class TestHiddenReturns:
    """What the run keeps is untouched; what it writes down is masked."""

    _KEY = "the-run-key-0123456789abcdef"

    def _output(self) -> StepOutput:
        return StepOutput(value={"api_key": self._KEY, "full_mock_url": "http://engine/mock/x"})

    def test_a_secret_output_is_hidden_without_being_asked(self) -> None:
        hide_secrets(MockEndpointStep, _definition("mock/api"), self._output())

        assert mask(self._KEY) == "***"

    def test_hidden_false_shows_a_secret_output(self) -> None:
        returns = {"api_key": ReturnFieldDefinition(type="string", hidden=False)}
        hide_secrets(MockEndpointStep, _definition("mock/api", returns), self._output())

        assert mask(self._KEY) == self._KEY

    def test_hidden_true_hides_any_return(self) -> None:
        returns = {"full_mock_url": ReturnFieldDefinition(type="string", hidden=True)}
        hide_secrets(MockEndpointStep, _definition("mock/api", returns), self._output())

        assert mask("http://engine/mock/x") == "***"

    def test_the_flag_is_part_of_the_returns_syntax(self) -> None:
        entry = ReturnFieldDefinition.model_validate({"type": "string", "hidden": True})
        assert entry.hidden is True


class TestTheReflexiveAsset:
    @pytest.fixture()
    def provider(self, context: MagicMock) -> MagicMock:
        provider = MagicMock()
        provider.create_asset.return_value = {"@id": "created"}
        context.dataspace.engine_provider.return_value = provider
        context.infrastructure.engine.connector.management_url = "https://engine/management"
        return provider

    async def _offer(self, context: MagicMock, asset: dict[str, Any]) -> Any:
        mock = (await _register(context, "/companycertificate/push"))["mock"]
        return await CreateMockAssetStep().invoke(
            {"asset": asset, "mock": mock},
            context,
            _definition("connector/provider/create_mock_asset"),
        )

    @pytest.mark.asyncio
    async def test_the_data_address_is_the_mock_and_carries_its_key(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        output = await self._offer(
            context,
            {
                "asset_id": "testlab-ccmapi-run-1",
                "dct_type": "https://w3id.org/catenax/taxonomy#CCMAPI",
                "dct_subject": "https://w3id.org/catenax/taxonomy#CCMAPIsubject",
                "version": "3.0",
            },
        )

        assert output.value["asset_id"] == "testlab-ccmapi-run-1"
        kwargs = provider.create_asset.call_args.kwargs
        header, key = required_header("/companycertificate/push", "POST")
        assert kwargs["base_url"] == "http://localhost:8080/runs/run-1"
        assert kwargs["headers"] == {header: key}
        assert kwargs["dct_subject"] == "https://w3id.org/catenax/taxonomy#CCMAPIsubject"
        assert kwargs["proxy_params"]["proxyBody"] == "true"
        context.dataspace.provider.assert_not_called()

    @pytest.mark.asyncio
    async def test_without_an_id_the_asset_is_named_after_the_run(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        output = await self._offer(context, {"dct_type": "cx-taxo:CCMAPI"})

        assert output.value["asset_id"] == "testlab-mock-run-1"

    @pytest.mark.asyncio
    async def test_an_asset_left_by_an_earlier_run_is_an_error(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        provider.create_asset.side_effect = ValueError("HTTP 409 conflict")

        with pytest.raises(AuthoringError, match="earlier run's key"):
            await self._offer(context, {"asset_id": "testlab-fixed"})

    @pytest.mark.asyncio
    async def test_a_public_mock_cannot_be_offered(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        mock = (await _register(context, public=True))["mock"]

        with pytest.raises(AuthoringError, match="requires no key"):
            await CreateMockAssetStep().invoke(
                {"asset": {"asset_id": "a"}, "mock": mock},
                context,
                _definition("connector/provider/create_mock_asset"),
            )

    def test_the_config_cannot_name_what_the_mock_supplies(self) -> None:
        mock = {"path": "/x", "method": "POST", "base_mock_url": "b", "full_mock_url": "f"}
        with pytest.raises(ValidationError, match="takes base_url"):
            CreateMockAssetParams(asset={"base_url": "http://elsewhere"}, mock=mock)


class TestTheServer:
    @pytest.fixture()
    def client(self, tmp_path: Path) -> Iterator[TestClient]:
        set_callback_manager(CallbackManager())
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
        registered = await _register(context)
        manager.refuse(_KEY, "POST")
        manager.refuse(_KEY, "POST")

        with pytest.raises(RuntimeError, match=r"2 call\(s\) reached the mock without the key"):
            await WaitForCallStep().invoke(
                {"mock": registered["mock"], "timeout_s": 0.01},
                context,
                _definition("mock/wait/http_request"),
            )

    @pytest.mark.asyncio
    async def test_a_timeout_with_nothing_refused_says_only_that(self, context: MagicMock) -> None:
        set_callback_manager(CallbackManager())
        registered = await _register(context)

        with pytest.raises(RuntimeError) as raised:
            await WaitForCallStep().invoke(
                {"mock": registered["mock"], "timeout_s": 0.01},
                context,
                _definition("mock/wait/http_request"),
            )
        assert "refused" not in str(raised.value)


class TestARefusedCallFailsTheWait:
    """A call the mock turns away ends the wait at once, saying why.

    The wait runs on the test's loop and the call arrives on the server's
    thread, as it does in a run: the refusal has to cross from one to the
    other, and a wait that only noticed it at its timeout would fail these
    tests by taking the whole of it.
    """

    _TIMEOUT_S = 10.0

    @pytest.fixture()
    def manager(self) -> CallbackManager:
        manager = CallbackManager()
        set_callback_manager(manager)
        return manager

    @pytest.fixture()
    def client(self, manager: CallbackManager, tmp_path: Path) -> Iterator[TestClient]:
        app = create_app(config=TestlabConfig(storage_dir=tmp_path, logs_dir=tmp_path))
        with TestClient(app) as client:
            yield client

    async def _wait_through(
        self,
        context: MagicMock,
        manager: CallbackManager,
        client: TestClient,
        call: dict[str, Any],
        step: type[WaitForCallStep] = WaitForCallStep,
        **params: Any,
    ) -> tuple[Any, Any, float]:
        """Wait on the mock at ``_PATH`` while *call* is made.

        Returns the answer the caller got, what the wait step ended with, and
        the seconds between the call and that end. A header written as ``...``
        in *call* carries the run's key.
        """
        registered = await _register(context)
        key = registered["api_key"]
        waiting = asyncio.create_task(
            step().invoke(
                {"mock": registered["mock"], "timeout_s": self._TIMEOUT_S, **params},
                context,
                _definition(step.__name__),
            )
        )
        while not manager.awaited():
            await asyncio.sleep(0.01)
        started = time.monotonic()
        headers = {
            name: key if value is ... else value for name, value in call.get("headers", {}).items()
        }
        answer = await asyncio.to_thread(
            client.request,
            call.get("method", "POST"),
            call.get("path", _PATH),
            headers=headers,
            json={},
        )
        try:
            outcome: Any = await waiting
        except MockCallRefusedError as refused:
            outcome = refused
        return answer, outcome, time.monotonic() - started

    @pytest.mark.asyncio
    async def test_a_call_without_the_key_fails_the_wait(
        self, context: MagicMock, manager: CallbackManager, client: TestClient
    ) -> None:
        answer, outcome, seconds = await self._wait_through(context, manager, client, {})

        assert answer.status_code == 401
        assert isinstance(outcome, MockCallRefusedError)
        assert MISSING_KEY in str(outcome)
        assert outcome.code == "MOCK_CALL_REFUSED"
        assert outcome.diagnostics["reason"] == MISSING_KEY
        assert outcome.diagnostics["expected"] == {"method": "POST", "path": _PATH}
        assert seconds < self._TIMEOUT_S / 2
        assert manager.refused(_KEY, "POST") == 1

    @pytest.mark.asyncio
    async def test_a_call_with_another_key_fails_the_wait(
        self, context: MagicMock, manager: CallbackManager, client: TestClient
    ) -> None:
        call = {"headers": {"x-api-key": "f" * 64}}
        answer, outcome, _ = await self._wait_through(context, manager, client, call)

        assert answer.status_code == 401
        assert isinstance(outcome, MockCallRefusedError)
        assert WRONG_KEY in str(outcome)
        assert "f" * 64 not in str(outcome)

    @pytest.mark.asyncio
    async def test_a_call_with_the_key_on_another_path_fails_the_wait(
        self, context: MagicMock, manager: CallbackManager, client: TestClient
    ) -> None:
        call = {"path": "/uniqueidpush/wrong", "headers": {"x-api-key": ...}}
        answer, outcome, _ = await self._wait_through(context, manager, client, call)

        assert answer.status_code == 404
        assert isinstance(outcome, MockCallRefusedError)
        assert f"went to POST /uniqueidpush/wrong, not to POST {_PATH}" in str(outcome)

    @pytest.mark.asyncio
    async def test_a_call_with_another_method_fails_the_wait(
        self, context: MagicMock, manager: CallbackManager, client: TestClient
    ) -> None:
        call = {"method": "PUT", "headers": {"x-api-key": ...}}
        answer, outcome, _ = await self._wait_through(context, manager, client, call)

        assert answer.status_code == 404
        assert isinstance(outcome, MockCallRefusedError)
        assert f"went to PUT {_PATH}, not to POST {_PATH}" in str(outcome)

    @pytest.mark.asyncio
    async def test_the_dataplane_wait_names_the_asset_to_negotiate(
        self, context: MagicMock, manager: CallbackManager, client: TestClient
    ) -> None:
        context.infrastructure.engine.connector.dsp_url = "https://engine/api/v1/dsp"
        context.infrastructure.engine.connector.participant_id = "did:web:engine"
        _, outcome, _ = await self._wait_through(
            context, manager, client, {}, WaitForDataplaneCallStep, asset_id="ccmapi-run-1"
        )

        assert isinstance(outcome, MockCallRefusedError)
        assert "engine connector's data plane, for asset ccmapi-run-1" in str(outcome)

    @pytest.mark.asyncio
    async def test_the_right_call_ends_the_wait_well(
        self, context: MagicMock, manager: CallbackManager, client: TestClient
    ) -> None:
        call = {"headers": {"X-Api-Key": ...}}
        answer, outcome, _ = await self._wait_through(context, manager, client, call)

        assert answer.status_code == 200
        assert outcome.value["request_path"] == _PATH

    @pytest.mark.asyncio
    async def test_a_keyless_call_elsewhere_is_pinned_on_no_wait(
        self, context: MagicMock, manager: CallbackManager, client: TestClient
    ) -> None:
        """Anyone can dial an address nobody opened; that says nothing about this run."""
        await _register(context)
        waiting = asyncio.create_task(manager.wait(_KEY, "POST", 0.5))
        while not manager.awaited():
            await asyncio.sleep(0.01)

        answer = await asyncio.to_thread(client.post, "/somewhere/else", json={})

        assert answer.status_code == 404
        assert (await waiting).timed_out


class TestARefusalOutlivesNoRun:
    def test_a_refusal_with_no_open_listener_is_dropped(self) -> None:
        manager = CallbackManager()

        assert manager.reject(_PATH, "POST", MISSING_KEY) is False
        assert manager._buffered == {}

    @pytest.mark.asyncio
    async def test_a_mock_armed_again_after_a_refusal_starts_clean(self) -> None:
        manager = CallbackManager()
        manager.register(_PATH, "POST")
        assert manager.reject(_PATH, "POST", MISSING_KEY)

        manager.register(_PATH, "POST")

        assert (await manager.wait(_PATH, "POST", 0.05)).timed_out

    def test_a_listener_of_an_ended_run_is_replaced(self) -> None:
        manager = CallbackManager()
        ended = asyncio.new_event_loop()
        manager._listeners[f"POST:{_PATH}"] = ended.create_future()
        ended.close()

        assert manager.reject(_PATH, "POST", MISSING_KEY) is False

        async def rearm() -> asyncio.AbstractEventLoop:
            manager.register(_PATH, "POST")
            return manager._listeners[f"POST:{_PATH}"].get_loop()

        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(rearm()) is loop
        finally:
            loop.close()

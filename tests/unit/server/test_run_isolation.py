################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Two runs on one mock server never share a mock, a key or a wait.

An engine runs several TCKs at once in one process, for different tenants, and
one server answers all their mocks. Two runs of one TCK register the same path;
two different TCKs may as well. Every case here has both runs registered at
once, and checks that a call reaches the run it was addressed to and no other —
by the run's own address, by the key it carries on a bare path — that a call
that names neither reaches nobody, and that one run ending leaves the other's
mocks standing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
from starlette.testclient import TestClient

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import StepDefinition, StepStatus
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.server.app import create_app
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.inbound.run_scope import acting_for, scoped
from tractusx_testlab.server.mock_registry import (
    WRONG_KEY,
    MockRequest,
    MockResponse,
    clear_callback_manager,
    clear_mocks,
    get_mock,
    register_mock,
    release_mocks,
    required_header,
    run_key,
    set_callback_manager,
)
from tractusx_testlab.steps.connector.provision.mock_asset import CreateMockAssetStep
from tractusx_testlab.steps.mock.api import MockEndpointStep
from tractusx_testlab.steps.mock.dtr import MockDtrStep
from tractusx_testlab.steps.mock.wait import MockCallRefusedError, WaitForCallStep

_PATH = "/companycertificate/status"


def _definition(uses: str) -> StepDefinition:
    return StepDefinition(id="s", uses=uses)


def _run(job_id: str) -> MagicMock:
    """A step context of the run *job_id*, on a server published at localhost."""
    context = MagicMock()
    context.job.job_id = job_id
    context.config.server_port = 8100
    context.config.mock_public_url = None
    return context


async def _open(context: MagicMock, body: Any, path: str = _PATH, method: str = "POST") -> dict:
    output = await MockEndpointStep().invoke(
        {"path": path, "method": method, "response_body": body}, context, _definition("mock/api")
    )
    return output.value


def _address(opened: dict) -> str:
    """The path of the URL the run handed out, as the system under test calls it."""
    return urlsplit(opened["full_mock_url"]).path


def _key(opened: dict) -> dict[str, str]:
    return {"x-api-key": opened["api_key"]}


@pytest.fixture()
def manager() -> Iterator[CallbackManager]:
    manager = CallbackManager()
    set_callback_manager(manager)
    yield manager
    clear_mocks()
    clear_callback_manager()


@pytest.fixture()
def client(manager: CallbackManager, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(TestlabConfig(storage_dir=tmp_path, logs_dir=tmp_path), mode="mock")
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def run_a() -> MagicMock:
    return _run("run-a")


@pytest.fixture()
def run_b() -> MagicMock:
    return _run("run-b")


async def _waiting(manager: CallbackManager, context: MagicMock, mock: dict) -> asyncio.Task:
    """The run's wait on *mock*, once it is under way."""
    task = asyncio.create_task(
        WaitForCallStep().invoke(
            {"mock": mock, "timeout_s": 5}, context, _definition("mock/wait/http_request")
        )
    )
    key_path = scoped(str(context.job.job_id), mock["path"])
    while (key_path, "POST") not in manager.awaited():
        await asyncio.sleep(0.01)
    return task


async def _post(client: TestClient, path: str, **kwargs: Any) -> Any:
    """Call the server from another thread, as the system under test does."""
    return await asyncio.to_thread(client.post, path, **kwargs)


class TestTwoRunsOfOneTck:
    @pytest.mark.asyncio
    async def test_each_run_publishes_an_address_of_its_own(
        self, manager: CallbackManager, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a, b = await _open(run_a, {}), await _open(run_b, {})

        assert a["full_mock_url"] == f"http://localhost:8100/runs/run-a{_PATH}"
        assert b["full_mock_url"] == f"http://localhost:8100/runs/run-b{_PATH}"
        assert a["api_key"] != b["api_key"]

    @pytest.mark.asyncio
    async def test_each_address_answers_with_its_own_runs_mock(
        self, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a, b = await _open(run_a, {"run": "a"}), await _open(run_b, {"run": "b"})

        assert (await _post(client, _address(a), headers=_key(a))).json() == {"run": "a"}
        assert (await _post(client, _address(b), headers=_key(b))).json() == {"run": "b"}

    @pytest.mark.asyncio
    async def test_a_call_ends_only_the_wait_of_the_run_it_was_addressed_to(
        self, manager: CallbackManager, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a, b = await _open(run_a, {}), await _open(run_b, {})
        waiting_a = await _waiting(manager, run_a, a["mock"])
        waiting_b = await _waiting(manager, run_b, b["mock"])

        await _post(client, _address(a), headers=_key(a), json={"for": "a"})
        received_a = await asyncio.wait_for(waiting_a, 5)

        assert received_a.value["request_body"] == {"for": "a"}
        assert received_a.value["request_path"] == _PATH
        assert not waiting_b.done()

        await _post(client, _address(b), headers=_key(b), json={"for": "b"})
        assert (await asyncio.wait_for(waiting_b, 5)).value["request_body"] == {"for": "b"}

    @pytest.mark.asyncio
    async def test_one_runs_key_opens_nothing_of_the_other_run(
        self, manager: CallbackManager, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a, b = await _open(run_a, {}), await _open(run_b, {})
        waiting_a = await _waiting(manager, run_a, a["mock"])
        waiting_b = await _waiting(manager, run_b, b["mock"])

        answer = await _post(client, _address(b), headers=_key(a), json={"for": "a"})

        assert answer.status_code == 401
        with pytest.raises(MockCallRefusedError, match=WRONG_KEY):
            await asyncio.wait_for(waiting_b, 5)
        assert not waiting_a.done()
        waiting_a.cancel()

    @pytest.mark.asyncio
    async def test_a_bare_path_reaches_the_run_whose_key_it_carries(
        self, manager: CallbackManager, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        """An address wired in by hand, or forwarded without the run in it."""
        a, b = await _open(run_a, {"run": "a"}), await _open(run_b, {"run": "b"})
        waiting_a = await _waiting(manager, run_a, a["mock"])
        waiting_b = await _waiting(manager, run_b, b["mock"])

        answer = await _post(client, _PATH, headers=_key(b), json={"for": "b"})

        assert answer.json() == {"run": "b"}
        assert (await asyncio.wait_for(waiting_b, 5)).value["request_body"] == {"for": "b"}
        assert not waiting_a.done()
        waiting_a.cancel()

    @pytest.mark.asyncio
    async def test_a_bare_path_that_names_no_run_reaches_none(
        self, manager: CallbackManager, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a, b = await _open(run_a, {}), await _open(run_b, {})
        waiting_a = await _waiting(manager, run_a, a["mock"])
        waiting_b = await _waiting(manager, run_b, b["mock"])

        answer = await _post(client, _PATH, json={"for": "anyone"})

        assert answer.status_code == 409
        await asyncio.sleep(0.05)
        assert not waiting_a.done()
        assert not waiting_b.done()
        assert manager._buffered == {}
        assert manager.refused(scoped("run-a", _PATH), "POST") == 0
        assert manager.refused(scoped("run-b", _PATH), "POST") == 0
        waiting_a.cancel()
        waiting_b.cancel()


class TestTwoDifferentTcksOnOnePath:
    """One TCK's canned mock and another's registry stand on the same path."""

    _SHELLS = "/shell-descriptors"

    @pytest.mark.asyncio
    async def test_each_run_is_answered_by_its_own_tcks_mock(
        self, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a = await _open(run_a, {"result": ["canned"]}, path=self._SHELLS, method="GET")
        await MockDtrStep().invoke(
            {"id": "dtr", "shells": [{"id": "urn:b"}]}, run_b, _definition("mock/dtr")
        )

        from_a = await asyncio.to_thread(client.get, _address(a), headers=_key(a))
        from_b = await asyncio.to_thread(client.get, f"/runs/run-b{self._SHELLS}")

        assert from_a.json() == {"result": ["canned"]}
        assert from_b.json()["result"] == [{"id": "urn:b"}]

    @pytest.mark.asyncio
    async def test_a_bare_path_is_pinned_by_the_key_or_refused(
        self, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a = await _open(run_a, {"result": ["canned"]}, path=self._SHELLS, method="GET")
        await MockDtrStep().invoke(
            {"id": "dtr", "shells": [{"id": "urn:b"}]}, run_b, _definition("mock/dtr")
        )

        keyed = await asyncio.to_thread(client.get, self._SHELLS, headers=_key(a))
        unkeyed = await asyncio.to_thread(client.get, self._SHELLS)

        assert keyed.json() == {"result": ["canned"]}
        assert unkeyed.status_code == 409

    @pytest.mark.asyncio
    async def test_a_handler_is_told_the_path_the_test_wrote(
        self, client: TestClient, run_a: MagicMock
    ) -> None:
        seen: list[str] = []

        def handler(request: MockRequest) -> MockResponse:
            seen.append(request.path)
            return MockResponse(status_code=200)

        register_mock(_PATH, "POST", handler, run="run-a")

        assert (await _post(client, f"/runs/run-a{_PATH}")).status_code == 200
        assert seen == [_PATH]


class TestOneRunEnding:
    @pytest.mark.asyncio
    async def test_leaves_the_other_runs_mock_and_wait_standing(
        self, manager: CallbackManager, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        a, b = await _open(run_a, {"run": "a"}), await _open(run_b, {"run": "b"})
        waiting_b = await _waiting(manager, run_b, b["mock"])

        release_mocks("run-a")

        assert get_mock(_PATH, "POST", run="run-a") is None
        assert get_mock(_PATH, "POST", run="run-b") is not None
        assert all(not path.startswith("/runs/run-a/") for path, _ in manager.listening())
        assert (await _post(client, _address(a), headers=_key(a))).status_code == 404
        answer = await _post(client, _address(b), headers=_key(b), json={"for": "b"})
        assert answer.json() == {"run": "b"}
        assert (await asyncio.wait_for(waiting_b, 5)).value["request_body"] == {"for": "b"}

    @pytest.mark.asyncio
    async def test_its_bare_path_belongs_to_the_run_still_going(
        self, client: TestClient, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        await _open(run_a, {"run": "a"})
        b = await _open(run_b, {"run": "b"})

        release_mocks("run-a")

        assert (await _post(client, _PATH, headers=_key(b))).json() == {"run": "b"}
        assert (await _post(client, _PATH)).status_code == 401


class TestTheAssetOffersItsOwnRunsKey:
    """``create_mock_asset`` reads the key of the mock it fronts — its own run's."""

    @pytest.mark.asyncio
    async def test_the_executing_run_names_whose_key(
        self, manager: CallbackManager, run_a: MagicMock, run_b: MagicMock
    ) -> None:
        await _open(run_a, {})
        await _open(run_b, {})

        with acting_for("run-b"):
            assert required_header(_PATH, "POST") == ("x-api-key", run_key("run-b"))
        with acting_for("run-a"):
            assert required_header(_PATH, "POST") == ("x-api-key", run_key("run-a"))
        assert required_header(_PATH, "POST") is None

    @pytest.mark.asyncio
    async def test_the_runner_runs_every_step_as_its_runs(
        self, manager: CallbackManager, run_a: MagicMock, mock_context: MagicMock
    ) -> None:
        await _open(run_a, {})
        mock_context.job.job_id = "run-b"
        mock_context.config.server_port = 8100
        mock_context.config.mock_public_url = None
        b = await _open(mock_context, {})
        provider = MagicMock()
        provider.create_asset.return_value = {"@id": "created"}
        mock_context.dataspace.engine_provider.return_value = provider
        mock_context.infrastructure.engine.connector.management_url = "https://engine/management"
        offer = StepDefinition(
            id="offer",
            uses="connector/provider/create_mock_asset",
            with_={"asset": {"asset_id": "ccm-run-b", "dct_type": "cx:CCMAPI"}, "mock": b["mock"]},
        )

        result = await run_step(CreateMockAssetStep, offer, "offer", mock_context)

        assert result.status == StepStatus.PASSED, result.error
        kwargs = provider.create_asset.call_args.kwargs
        assert kwargs["headers"] == {"x-api-key": run_key("run-b")}
        assert kwargs["base_url"] == "http://localhost:8100/runs/run-b"

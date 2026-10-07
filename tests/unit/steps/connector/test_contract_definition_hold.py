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

"""What a paused run withdraws: the contract definitions it created, and nothing else."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.hold import RunHold
from tractusx_testlab.server.app import create_app
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import (
    MockResponse,
    clear_mocks,
    register_mock,
    set_callback_manager,
)
from tractusx_testlab.steps.connector.cleanup import DeleteContractDefinitionStep
from tractusx_testlab.steps.connector.provision.contract_definition import (
    CreateContractDefinitionStep,
)


class _Response:
    def __init__(self, status_code: int = 200, body: Any = None) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self) -> Any:
        return self._body


@pytest.fixture()
def provider() -> MagicMock:
    service = MagicMock()
    service.dataspace_version = "jupiter"
    service.contract_definitions.create.return_value = _Response(200, {"@id": "cd-1"})
    service.contract_definitions.delete.return_value = _Response(204)
    return service


@pytest.fixture()
def context(provider: MagicMock) -> MagicMock:
    ctx = attach_endpoint_url_stubs(MagicMock())
    ctx.dataspace.provider.return_value = provider
    ctx.hold = RunHold()
    return ctx


async def _create(context: MagicMock) -> None:
    await CreateContractDefinitionStep().invoke(
        {
            "contract_definition_id": "cd-1",
            "asset_id": "a",
            "access_policy_id": "p",
            "contract_policy_id": "p",
        },
        context,
        StepDefinition(id="cd", uses="connector/provider/create_contract_definition"),
    )


class TestTheDefinitionsARunCreates:
    @pytest.mark.asyncio
    async def test_are_recorded_on_its_hold(self, context: MagicMock) -> None:
        await _create(context)
        assert context.hold.offers == ["cd-1"]

    @pytest.mark.asyncio
    async def test_are_withdrawn_and_posted_again_as_they_were(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        await _create(context)
        sent = provider.contract_definitions.create.call_args.kwargs["obj"]

        assert context.hold._withdraw() == (["cd-1"], {})
        provider.contract_definitions.delete.assert_called_once_with(oid="cd-1")

        assert context.hold._restore(["cd-1"]) == (["cd-1"], {})
        assert provider.contract_definitions.create.call_args.kwargs["obj"] is sent

    @pytest.mark.asyncio
    async def test_a_refused_delete_is_reported_as_kept(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        await _create(context)
        provider.contract_definitions.delete.return_value = _Response(409)

        withdrawn, kept = context.hold._withdraw()

        assert withdrawn == []
        assert "409" in kept["cd-1"]

    @pytest.mark.asyncio
    async def test_one_that_was_already_there_is_not_the_runs(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        provider.contract_definitions.create.return_value = _Response(409)
        await _create(context)
        assert context.hold.offers == []

    @pytest.mark.asyncio
    async def test_one_the_run_deletes_is_forgotten(self, context: MagicMock) -> None:
        await _create(context)
        await DeleteContractDefinitionStep().invoke(
            {"contract_definition_id": "cd-1"},
            context,
            StepDefinition(id="rm", uses="connector/provider/delete_contract_definition"),
        )
        assert context.hold.offers == []


class TestTheServerWhileARunIsHeld:
    @pytest.fixture()
    def client(self, tmp_path: Path) -> Iterator[TestClient]:
        set_callback_manager(CallbackManager())
        app = create_app(config=TestlabConfig(storage_dir=tmp_path, logs_dir=tmp_path))
        register_mock("/push", "POST", MockResponse(status_code=200, body={"ok": True}))
        with TestClient(app) as client:
            yield client
        clear_mocks()

    def _hold(self, client: TestClient) -> None:
        jobs = client.app.state.player.jobs
        job = jobs.create("tck")
        jobs.hold(job.job_id, True)

    def test_a_mock_answers_404_and_resolves_nothing(self, client: TestClient) -> None:
        self._hold(client)

        answer = client.post("/push", json={"a": 1})

        assert answer.status_code == 404
        assert "paused" in answer.json()["detail"]
        assert client.app.state.callbacks._buffered == {}

    def test_a_callback_route_answers_404_too(self, client: TestClient) -> None:
        self._hold(client)
        assert client.post("/callbacks/push", json={}).status_code == 404

    def test_it_answers_again_once_the_hold_ends(self, client: TestClient) -> None:
        self._hold(client)
        jobs = client.app.state.player.jobs
        for job in jobs.list_jobs():
            jobs.hold(job.job_id, False)

        assert client.post("/push", json={"a": 1}).status_code == 200

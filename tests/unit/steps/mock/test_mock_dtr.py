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

"""Tests for mock/dtr — the protocol-aware Digital Twin Registry mock."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.server.mock_registry import clear_mocks, resolve_mock
from tractusx_testlab.steps.digital_twin_registry.consumer import ShellLookupParams
from tractusx_testlab.steps.mock.dtr import MockDtrStep


def _b64url(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _criteria(*entries: dict) -> list[str]:
    """The criteria as ``GET /lookup/shells`` takes them: one value per criterion."""
    return [_b64url(json.dumps(entry)) for entry in entries]


@pytest.fixture(autouse=True)
def _reset_registry():
    clear_mocks()
    yield
    clear_mocks()


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinition:
    return StepDefinition(id="dtr", uses="mock/dtr")


_SHELL = {
    "id": "urn:uuid:shell-1",
    "specificAssetIds": [{"name": "partInstanceId", "value": "P-1"}],
}


class TestMockDtrStep:
    @pytest.mark.asyncio
    async def test_requires_id(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="id: required key 'id' is missing"):
            await MockDtrStep().invoke({}, context, _definition())

    @pytest.mark.asyncio
    async def test_list_shells_returns_configured_shells(self, context: StepContext) -> None:
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        mock = resolve_mock(
            "/shell-descriptors",
            "GET",
            headers={},
            query_params={},
            body=None,
        )
        assert mock.status_code == 200
        assert mock.body["result"] == [_SHELL]

    @pytest.mark.asyncio
    async def test_get_shell_by_encoded_id(self, context: StepContext) -> None:
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        mock = resolve_mock(
            f"/shell-descriptors/{_b64url(_SHELL['id'])}",
            "GET",
            headers={},
            query_params={},
            body=None,
        )
        assert mock.status_code == 200
        assert mock.body == _SHELL

    @pytest.mark.asyncio
    async def test_get_shell_with_unregistered_id_has_no_route(self, context: StepContext) -> None:
        # Only known shell ids get a dedicated route; an id no one registered
        # falls through to the server's generic 404, rather than this mock.
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        mock = resolve_mock(
            f"/shell-descriptors/{_b64url('urn:uuid:missing')}",
            "GET",
            headers={},
            query_params={},
            body=None,
        )
        assert mock is None

    @pytest.mark.asyncio
    async def test_register_new_shell_then_fetch_it(self, context: StepContext) -> None:
        await MockDtrStep().invoke({"id": "dtr1", "shells": []}, context, _definition())
        new_shell = {"id": "urn:uuid:new-shell"}
        register = resolve_mock(
            "/shell-descriptors",
            "POST",
            headers={},
            query_params={},
            body=new_shell,
        )
        assert register.status_code == 201

        fetched = resolve_mock(
            f"/shell-descriptors/{_b64url(new_shell['id'])}",
            "GET",
            headers={},
            query_params={},
            body=None,
        )
        assert fetched.status_code == 200
        assert fetched.body == new_shell

    @pytest.mark.asyncio
    async def test_lookup_by_specific_asset_ids_matches(self, context: StepContext) -> None:
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        mock = resolve_mock(
            "/lookup/shells",
            "GET",
            headers={},
            query_params={"assetIds": _criteria({"name": "partInstanceId", "value": "P-1"})},
            body=None,
        )
        assert mock.status_code == 200
        assert mock.body["result"] == [_SHELL["id"]]

    @pytest.mark.asyncio
    async def test_lookup_no_match_returns_empty(self, context: StepContext) -> None:
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        mock = resolve_mock(
            "/lookup/shells",
            "GET",
            headers={},
            query_params={
                "assetIds": _criteria({"name": "partInstanceId", "value": "does-not-exist"})
            },
            body=None,
        )
        assert mock.body["result"] == []

    @pytest.mark.asyncio
    async def test_every_repeated_criterion_has_to_match(self, context: StepContext) -> None:
        """Several criteria travel as several ``assetIds`` values, and all of them count."""
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        both = _criteria(
            {"name": "partInstanceId", "value": "P-1"},
            {"name": "digitalTwinType", "value": "PartInstance"},
        )
        mock = resolve_mock(
            "/lookup/shells", "GET", headers={}, query_params={"assetIds": both}, body=None
        )
        # The shell carries the first criterion and not the second, so it is not
        # a match — a registry that saw only the last value would have said it was.
        assert mock.body["result"] == []

    @pytest.mark.asyncio
    async def test_the_encoding_the_consumer_step_sends_is_the_one_the_mock_reads(
        self, context: StepContext
    ) -> None:
        """The seam this mock exists to serve: the engine's own lookup step.

        The two sides were tested only against themselves and disagreed —
        ``lookup_shell`` sends one base64url-encoded object per criterion (AAS
        v3), the mock read one value holding the whole list — so the mock raised
        ``AttributeError`` on a request the engine actually makes.
        """
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        params = ShellLookupParams.model_validate(
            {
                "dataplane_url": "https://dataplane.example",
                "edr_token": "token",
                "specific_asset_ids": [{"name": "partInstanceId", "value": "P-1"}],
            }
        )
        # Exactly what the step hands the HTTP client as its query.
        mock = resolve_mock(
            "/lookup/shells",
            "GET",
            headers={},
            query_params={"assetIds": params.asset_id_query()},
            body=None,
        )
        assert mock.status_code == 200
        assert mock.body["result"] == [_SHELL["id"]]

    @pytest.mark.asyncio
    async def test_a_value_holding_the_whole_list_is_refused_by_name(
        self, context: StepContext
    ) -> None:
        """The wrong encoding gets an answer that says which one to use."""
        await MockDtrStep().invoke({"id": "dtr1", "shells": [_SHELL]}, context, _definition())
        whole_list = _b64url(json.dumps([{"name": "partInstanceId", "value": "P-1"}]))
        mock = resolve_mock(
            "/lookup/shells",
            "GET",
            headers={},
            query_params={"assetIds": [whole_list]},
            body=None,
        )
        assert mock.status_code == 400
        assert "one base64url-encoded SpecificAssetId object" in mock.body["error"]

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Tests for the ``labs/connector/provider/query_*`` steps — listing what the connector holds."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.extensions.labs.steps.provider_query import (
    _PAGE_SIZE,
    QueryAssetsStep,
    QueryContractDefinitionsStep,
    QueryPoliciesStep,
)

_EDC_ID = "https://w3id.org/edc/v0.0.1/ns/id"


def _answer(body: Any, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body
    return response


def _provider(controller: str, *pages: Any) -> MagicMock:
    provider = MagicMock()
    provider.dataspace_version = "saturn"
    getattr(provider, controller).query.side_effect = list(pages)
    return provider


def _definition(oid: str, asset: Any, access: str = "ap", contract: str = "cp") -> dict:
    return {
        "@id": oid,
        "accessPolicyId": access,
        "contractPolicyId": contract,
        "assetsSelector": {"operandLeft": _EDC_ID, "operator": "=", "operandRight": asset},
    }


class TestQueryAssets:
    @pytest.mark.asyncio
    async def test_keeps_only_the_ids_with_the_prefix(self, mock_context: MagicMock) -> None:
        mock_context.dataspace.provider.return_value = _provider(
            "assets", _answer([{"@id": "testlab-a"}, {"@id": "other"}, {"@id": "testlab-b"}])
        )

        output = await QueryAssetsStep().invoke({"id_prefix": "testlab-"}, mock_context, None)

        assert output.value == {"asset_ids": ["testlab-a", "testlab-b"]}

    @pytest.mark.asyncio
    async def test_reads_every_page(self, mock_context: MagicMock) -> None:
        full = [{"@id": f"a{i}"} for i in range(_PAGE_SIZE)]
        provider = _provider("assets", _answer(full), _answer([{"@id": "last"}]))
        mock_context.dataspace.provider.return_value = provider

        output = await QueryAssetsStep().invoke({}, mock_context, None)

        assert len(output.value["asset_ids"]) == _PAGE_SIZE + 1
        assert provider.assets.query.call_count == 2

    @pytest.mark.asyncio
    async def test_a_refused_query_fails_with_the_status(self, mock_context: MagicMock) -> None:
        mock_context.dataspace.provider.return_value = _provider("assets", _answer(None, 401))

        with pytest.raises(ValueError, match="answered 401"):
            await QueryAssetsStep().invoke({}, mock_context, None)


class TestQueryPolicies:
    @pytest.mark.asyncio
    async def test_an_empty_prefix_keeps_every_id(self, mock_context: MagicMock) -> None:
        mock_context.dataspace.provider.return_value = _provider(
            "policies", _answer([{"@id": "p1"}, {"@id": "p2"}])
        )

        output = await QueryPoliciesStep().invoke({}, mock_context, None)

        assert output.value == {"policy_ids": ["p1", "p2"]}


class TestQueryContractDefinitions:
    @pytest.mark.asyncio
    async def test_finds_a_generated_definition_by_the_asset_it_offers(
        self, mock_context: MagicMock
    ) -> None:
        mock_context.dataspace.provider.return_value = _provider(
            "contract_definitions",
            _answer([_definition("uuid-1", "testlab-x"), _definition("uuid-2", "other")]),
        )

        output = await QueryContractDefinitionsStep().invoke(
            {"asset_id_prefix": "testlab-"}, mock_context, None
        )

        assert output.value == {
            "contract_definition_ids": ["uuid-1"],
            "policy_ids": ["ap", "cp"],
            "asset_ids": ["testlab-x"],
        }

    @pytest.mark.asyncio
    async def test_reads_a_selector_list_and_an_in_operand(self, mock_context: MagicMock) -> None:
        entry = _definition("cd", ["a1", "a2"])
        entry["assetsSelector"] = [entry["assetsSelector"]]
        mock_context.dataspace.provider.return_value = _provider(
            "contract_definitions", _answer([entry])
        )

        output = await QueryContractDefinitionsStep().invoke({}, mock_context, None)

        assert output.value["asset_ids"] == ["a1", "a2"]

    @pytest.mark.asyncio
    async def test_lists_a_policy_two_definitions_share_once(self, mock_context: MagicMock) -> None:
        mock_context.dataspace.provider.return_value = _provider(
            "contract_definitions",
            _answer(
                [_definition("cd-1", "a", "shared", "c1"), _definition("cd-2", "b", "shared", "c2")]
            ),
        )

        output = await QueryContractDefinitionsStep().invoke(
            {"id_prefix": "cd-"}, mock_context, None
        )

        assert output.value["policy_ids"] == ["shared", "c1", "c2"]

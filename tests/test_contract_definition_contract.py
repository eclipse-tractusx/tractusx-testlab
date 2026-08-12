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

"""Contract tests for ``connector/provider/create_contract_definition``."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.provision import (
    CreateContractDefinitionParams,
    CreateContractDefinitionStep,
)

_ASSET_ID_OPERAND = "https://w3id.org/edc/v0.0.1/ns/id"


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
    return service


@pytest.fixture()
def context(provider: MagicMock) -> MagicMock:
    ctx = attach_endpoint_url_stubs(MagicMock())
    ctx.get_provider_base_url.return_value = "https://provider.example.com"
    ctx.get_provider_service.return_value = provider
    return ctx


def _definition() -> StepDefinition:
    return StepDefinition(
        id="cd", uses="connector/provider/create_contract_definition"
    )


def _sent(provider: MagicMock) -> dict:
    """The JSON body the step actually posted to the connector."""
    return json.loads(provider.contract_definitions.create.call_args.kwargs["obj"].to_data())


class TestOneNameBothDirections:
    """C14 — the id goes in and comes back under a single name."""

    @pytest.mark.asyncio
    async def test_the_given_id_is_the_id_reported_back(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        output = await CreateContractDefinitionStep().invoke(
            {
                "contract_definition_id": "cd-1",
                "access_policy_id": "ap-1",
                "contract_policy_id": "cp-1",
                "asset_id": "asset-1",
            },
            context,
            _definition(),
        )
        assert output.value["contract_definition_id"] == "cd-1"

    @pytest.mark.asyncio
    async def test_an_omitted_id_is_invented_and_reported(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        output = await CreateContractDefinitionStep().invoke(
            {"access_policy_id": "ap-1", "contract_policy_id": "cp-1", "asset_id": "a"},
            context,
            _definition(),
        )
        assert output.value["contract_definition_id"] == _sent(provider)["@id"]

    def test_the_old_spellings_no_longer_bind(self) -> None:
        params = CreateContractDefinitionParams(
            contract_id="cd-1", usage_policy_id="cp-1"
        )
        assert (params.contract_definition_id, params.contract_policy_id) == ("", "")


class TestPolicyWiring:
    """C23 — the policy field is ``contract_policy_id``, as the EDC calls it."""

    @pytest.mark.asyncio
    async def test_both_policies_reach_the_connector(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        await CreateContractDefinitionStep().invoke(
            {
                "access_policy_id": "ap-1",
                "contract_policy_id": "cp-1",
                "asset_id": "asset-1",
            },
            context,
            _definition(),
        )
        sent = _sent(provider)
        assert (sent["accessPolicyId"], sent["contractPolicyId"]) == ("ap-1", "cp-1")

    def test_a_policy_step_output_is_unwrapped_to_its_id(self) -> None:
        """Wiring the whole ``create_policy`` output in must still work."""
        params = CreateContractDefinitionParams(contract_policy_id={"policy_id": "cp-1"})
        assert params.contract_policy_id == "cp-1"


class TestAssetSelector:
    """C29 — a definition can offer more than one asset."""

    def test_a_bare_asset_id_becomes_a_one_criterion_selector(self) -> None:
        params = CreateContractDefinitionParams(asset_id="asset-1")
        assert params.assets_selector() == [
            {"operandLeft": _ASSET_ID_OPERAND, "operator": "=", "operandRight": "asset-1"}
        ]

    def test_criteria_are_sent_in_the_shape_the_edc_expects(self) -> None:
        params = CreateContractDefinitionParams(
            asset_selector=[
                {"operand_left": "https://purl.org/dc/terms/type", "operand_right": "CCMAPI"},
                {"operand_left": "version", "operator": "=", "operand_right": "3.0"},
            ]
        )
        assert params.assets_selector() == [
            {
                "operandLeft": "https://purl.org/dc/terms/type",
                "operator": "=",
                "operandRight": "CCMAPI",
            },
            {"operandLeft": "version", "operator": "=", "operandRight": "3.0"},
        ]

    def test_the_selector_wins_over_a_single_asset_id(self) -> None:
        params = CreateContractDefinitionParams(
            asset_id="asset-1",
            asset_selector=[{"operand_left": "version", "operand_right": "3.0"}],
        )
        assert params.assets_selector() == [
            {"operandLeft": "version", "operator": "=", "operandRight": "3.0"}
        ]

    @pytest.mark.asyncio
    async def test_the_selector_reaches_the_connector(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        await CreateContractDefinitionStep().invoke(
            {
                "access_policy_id": "ap-1",
                "contract_policy_id": "cp-1",
                "asset_selector": [
                    {"operand_left": "version", "operand_right": "3.0"}
                ],
            },
            context,
            _definition(),
        )
        assert _sent(provider)["assetsSelector"] == [
            {"operandLeft": "version", "operator": "=", "operandRight": "3.0"}
        ]


class TestAlreadyProvisioned:
    @pytest.mark.asyncio
    async def test_a_409_is_reported_rather_than_raised(
        self, context: MagicMock, provider: MagicMock
    ) -> None:
        """Re-running a script against a provisioned provider must not fail."""
        provider.contract_definitions.create.return_value = _Response(409)

        output = await CreateContractDefinitionStep().invoke(
            {"access_policy_id": "ap-1", "contract_policy_id": "cp-1", "asset_id": "a"},
            context,
            _definition(),
        )

        assert output.response.status_code == 409

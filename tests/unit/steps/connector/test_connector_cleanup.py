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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Unit tests for DeleteAssetStep, DeletePolicyStep, and DeleteContractDefinitionStep."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.steps.connector.cleanup import (
    DeleteAssetStep,
    DeleteContractDefinitionStep,
    DeletePolicyStep,
)

_BASE_URL = "https://provider.example.com"


def _make_delete_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    return resp


@pytest.fixture()
def ctx() -> MagicMock:
    """StepContext mock with working variable store and provider service."""
    mock = MagicMock()
    variables: dict[str, Any] = {}

    def _set(name: str, value: Any) -> None:
        variables[name] = value

    def _get(name: str, default: Any = None) -> Any:
        return variables.get(name, default)

    mock.set_variable = MagicMock(side_effect=_set)
    mock.get_variable = MagicMock(side_effect=_get)
    mock.get_str = MagicMock(side_effect=lambda n, d="": str(_get(n, d) or d))
    mock.variables = variables
    mock.dataspace.provider_base_url.return_value = _BASE_URL
    return attach_endpoint_url_stubs(mock)


@pytest.fixture()
def definition() -> MagicMock:
    return MagicMock()


class TestDeleteAssetStep:
    """Tests for DeleteAssetStep — calls provider.assets.delete(oid=...)."""

    @pytest.mark.asyncio
    async def test_calls_assets_delete_with_asset_id_from_params(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        # Arrange
        provider = MagicMock()
        provider.assets.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider

        # Act
        await DeleteAssetStep().invoke(
            raw_params={"asset_id": "urn:asset:001"}, context=ctx, definition=definition
        )

        # Assert — SDK controller called with the right ID
        provider.assets.delete.assert_called_once_with(oid="urn:asset:001")

    @pytest.mark.asyncio
    async def test_falls_back_to_context_variable_when_param_absent(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.assets.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider
        ctx.set_variable("asset_id", "urn:asset:from-context")

        await DeleteAssetStep().invoke(raw_params={}, context=ctx, definition=definition)

        provider.assets.delete.assert_called_once_with(oid="urn:asset:from-context")

    @pytest.mark.asyncio
    async def test_response_status_reflects_controller_response(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.assets.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider

        output = await DeleteAssetStep().invoke(
            raw_params={"asset_id": "urn:asset:001"}, context=ctx, definition=definition
        )

        assert output.response.status_code == 204
        assert output.request.method == "DELETE"

    @pytest.mark.asyncio
    async def test_status_204_when_controller_returns_none(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        """Provider controller returns None on successful delete in some SDK versions."""
        provider = MagicMock()
        provider.assets.delete.return_value = None
        ctx.dataspace.provider.return_value = provider

        output = await DeleteAssetStep().invoke(
            raw_params={"asset_id": "urn:asset:001"}, context=ctx, definition=definition
        )

        assert output.response.status_code == 204


class TestDeletePolicyStep:
    """Tests for DeletePolicyStep — calls provider.policies.delete(oid=...)."""

    @pytest.mark.asyncio
    async def test_calls_policies_delete_with_policy_id_from_params(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.policies.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider

        await DeletePolicyStep().invoke(
            raw_params={"policy_id": "policy-uuid-001"}, context=ctx, definition=definition
        )

        provider.policies.delete.assert_called_once_with(oid="policy-uuid-001")

    @pytest.mark.asyncio
    async def test_falls_back_to_context_variable_when_param_absent(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.policies.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider
        ctx.set_variable("policy_id", "policy-from-context")

        await DeletePolicyStep().invoke(raw_params={}, context=ctx, definition=definition)

        provider.policies.delete.assert_called_once_with(oid="policy-from-context")

    @pytest.mark.asyncio
    async def test_response_uses_controller_status_code(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.policies.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider

        output = await DeletePolicyStep().invoke(
            raw_params={"policy_id": "policy-uuid-001"}, context=ctx, definition=definition
        )

        assert output.response.status_code == 204
        assert output.request.method == "DELETE"


class TestDeleteContractDefinitionStep:
    """Tests for DeleteContractDefinitionStep — calls provider.contract_definitions.delete(oid=...)."""

    @pytest.mark.asyncio
    async def test_calls_contract_definitions_delete_with_id_from_params(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.contract_definitions.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider

        await DeleteContractDefinitionStep().invoke(
            raw_params={"contract_definition_id": "contract-uuid-001"},
            context=ctx,
            definition=definition,
        )

        provider.contract_definitions.delete.assert_called_once_with(oid="contract-uuid-001")

    @pytest.mark.asyncio
    async def test_falls_back_to_context_variable_when_param_absent(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.contract_definitions.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider
        ctx.set_variable("contract_definition_id", "contract-from-context")

        await DeleteContractDefinitionStep().invoke(
            raw_params={}, context=ctx, definition=definition
        )

        provider.contract_definitions.delete.assert_called_once_with(oid="contract-from-context")

    @pytest.mark.asyncio
    async def test_response_uses_controller_status_code(
        self, ctx: MagicMock, definition: MagicMock
    ) -> None:
        provider = MagicMock()
        provider.contract_definitions.delete.return_value = _make_delete_response(204)
        ctx.dataspace.provider.return_value = provider

        output = await DeleteContractDefinitionStep().invoke(
            raw_params={"contract_definition_id": "contract-uuid-001"},
            context=ctx,
            definition=definition,
        )

        assert output.response.status_code == 204
        assert output.request.method == "DELETE"

    @pytest.mark.asyncio
    async def test_cleanup_method_is_noop(self, ctx: MagicMock) -> None:
        """cleanup() must not raise and must not call any service method."""
        provider = MagicMock()
        ctx.dataspace.provider.return_value = provider

        await DeleteContractDefinitionStep().cleanup(ctx)

        provider.contract_definitions.delete.assert_not_called()


#: The three delete steps, with the controller each one drives and the input
#: naming the resource — the same contract three times over.
_DELETE_STEPS = [
    (DeleteAssetStep, "assets", "asset_id", "urn:asset:001"),
    (DeletePolicyStep, "policies", "policy_id", "policy-uuid-001"),
    (
        DeleteContractDefinitionStep,
        "contract_definitions",
        "contract_definition_id",
        "contract-uuid-001",
    ),
]


class TestDeleteStepsPublishStatusCode:
    """Every delete step publishes the connector's answer as ``status_code``.

    A teardown asserts that the resource was really there (204) rather than
    already gone (404), so the code has to be a *declared* output — readable
    through ``returns:`` and published as a context variable — and not only a
    field of the HTTP record a script cannot name.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [204, 404])
    @pytest.mark.parametrize(("step_cls", "controller", "param", "oid"), _DELETE_STEPS)
    async def test_declares_the_status_the_connector_answered(
        self,
        ctx: MagicMock,
        definition: MagicMock,
        step_cls: Any,
        controller: str,
        param: str,
        oid: str,
        status: int,
    ) -> None:
        # Arrange
        provider = MagicMock()
        getattr(provider, controller).delete.return_value = _make_delete_response(status)
        ctx.dataspace.provider.return_value = provider

        # Act
        output = await step_cls().invoke(
            raw_params={param: oid}, context=ctx, definition=definition
        )

        # Assert — the status is the whole of the output, and it is published
        assert output.value == {"status_code": status}
        assert ctx.variables["status_code"] == status

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("step_cls", "controller", "param", "oid"), _DELETE_STEPS)
    async def test_reports_204_when_the_controller_answers_with_nothing(
        self,
        ctx: MagicMock,
        definition: MagicMock,
        step_cls: Any,
        controller: str,
        param: str,
        oid: str,
    ) -> None:
        """Some SDK versions return None from a successful delete."""
        provider = MagicMock()
        getattr(provider, controller).delete.return_value = None
        ctx.dataspace.provider.return_value = provider

        output = await step_cls().invoke(
            raw_params={param: oid}, context=ctx, definition=definition
        )

        assert output.value == {"status_code": 204}

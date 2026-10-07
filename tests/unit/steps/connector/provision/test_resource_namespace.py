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
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-6).
## It was reviewed and tested by a human committer.

"""Provider IDs and selectors stay inside the player's run namespace."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job, StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.connector.cleanup import (
    DeleteAssetStep,
    DeleteContractDefinitionStep,
    DeletePolicyStep,
)
from tractusx_testlab.steps.connector.provision.asset import CreateAssetStep, WizardCreateAssetStep
from tractusx_testlab.steps.connector.provision.contract_definition import (
    CreateContractDefinitionStep,
)
from tractusx_testlab.steps.connector.provision.policy import (
    CreatePolicyStep,
    WizardCreatePolicyStep,
)

PREFIX = "cx-test-suite:run-a-"


@pytest.fixture()
def ctx():
    real = StepContext(
        ServiceManager(), Job(job_id="run-a"), TestlabConfig(), resource_prefix=PREFIX
    )
    context = attach_endpoint_url_stubs(MagicMock())
    context.resource_prefix = real.resource_prefix
    context.resource_id = real.resource_id
    context.dataspace.provider.return_value.dataspace_version = "saturn"
    context.dataspace.provider.return_value.contract_definitions.create.return_value.status_code = (
        200
    )
    context.dataspace.provider.return_value.contract_definitions.create.return_value.json.return_value = {}
    return context


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step,params,method,key",
    [
        (
            CreateAssetStep,
            {"asset": {"asset_id": "asset", "base_url": "http://backend"}},
            "create_asset",
            "asset_id",
        ),
        (
            WizardCreateAssetStep,
            {"asset_id": "asset", "name": "Asset", "base_url": "http://backend"},
            "create_asset",
            "asset_id",
        ),
        (
            CreatePolicyStep,
            {"policy": {"policy_id": "policy", "permissions": [{"action": "use"}]}},
            "create_policy",
            "policy_id",
        ),
        (
            WizardCreatePolicyStep,
            {"policy_id": "policy", "permissions": [{"action": "use"}]},
            "create_policy",
            "policy_id",
        ),
    ],
)
async def test_all_creation_forms_scope_explicit_ids(ctx, step, params, method, key):
    output = await step().invoke(params, ctx, StepDefinition(uses="util/log"))
    sent = getattr(ctx.dataspace.provider(), method).call_args.kwargs[key]
    assert sent == PREFIX + ("asset" if key == "asset_id" else "policy")
    assert output.value[key] == sent


@pytest.mark.asyncio
async def test_generated_ids_are_scoped(ctx):
    output = await WizardCreatePolicyStep().invoke(
        {"permissions": [{"action": "use"}]}, ctx, StepDefinition(uses="util/log")
    )
    assert output.value["policy_id"].startswith(PREFIX)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selector", [None, [{"operand_left": "dct:type", "operator": "=", "operand_right": "CCMAPI"}]]
)
async def test_contract_definitions_scope_policies_and_asset_selectors(ctx, selector):
    params = {
        "contract_definition_id": "contract",
        "access_policy_id": "access",
        "contract_policy_id": PREFIX + "usage",
        "asset_id": "asset",
    }
    if selector:
        params["asset_selector"] = selector
    output = await CreateContractDefinitionStep().invoke(
        params, ctx, StepDefinition(uses="util/log")
    )
    sent = json.loads(
        ctx.dataspace.provider().contract_definitions.create.call_args.kwargs["obj"].to_data()
    )
    assert output.value["contract_definition_id"] == PREFIX + "contract"
    assert sent["accessPolicyId"] == PREFIX + "access"
    assert sent["contractPolicyId"] == PREFIX + "usage"
    criteria = sent["assetsSelector"]
    assert criteria[-1]["operandRight"] == PREFIX + "%"
    assert criteria[-1]["operator"] == "like"
    if selector is None:
        assert criteria[0]["operandRight"] == PREFIX + "asset"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step,key,controller",
    [
        (DeleteAssetStep, "asset_id", "assets"),
        (DeletePolicyStep, "policy_id", "policies"),
        (DeleteContractDefinitionStep, "contract_definition_id", "contract_definitions"),
    ],
)
async def test_deletion_uses_the_actual_created_resource_id(ctx, step, key, controller):
    value = PREFIX + "resource"
    await step().invoke({key: value}, ctx, StepDefinition(uses="util/log"))
    getattr(ctx.dataspace.provider(), controller).delete.assert_called_once_with(
        oid=PREFIX + "resource"
    )


@pytest.mark.asyncio
async def test_mock_asset_creation_and_listener_publish_the_same_scoped_id(ctx):
    from tractusx_testlab.steps.connector.provision.mock_asset import CreateMockAssetStep
    from tractusx_testlab.steps.mock._models import WaitForDataplaneCallParams
    from tractusx_testlab.steps.mock.wait import WaitForDataplaneCallStep

    mock = {
        "path": "/runs/run-a/callback",
        "method": "POST",
        "base_mock_url": "http://engine/runs/run-a",
        "full_mock_url": "http://engine/runs/run-a/callback",
    }
    ctx.infrastructure.engine.connector.management_url = "http://engine/management"
    ctx.dataspace.engine_provider.return_value.create_asset.return_value = {}
    with patch(
        "tractusx_testlab.steps.connector.provision.mock_asset.required_header",
        return_value=("x-api-key", "run-secret"),
    ):
        output = await CreateMockAssetStep().invoke(
            {"asset": {"asset_id": "mock-asset"}, "mock": mock},
            ctx,
            StepDefinition(uses="connector/provider/create_mock_asset"),
        )
    ctx.infrastructure.engine.connector.dsp_url = "http://engine/dsp"
    ctx.infrastructure.engine.connector.participant_id = "BPNL000000000001"
    listener = WaitForDataplaneCallStep().listener(
        WaitForDataplaneCallParams(mock=mock, asset_id="mock-asset"), ctx
    )
    assert output.value["asset_id"] == PREFIX + "mock-asset"
    assert listener.offer.asset_id == output.value["asset_id"]
    assert (
        ctx.dataspace.engine_provider().create_asset.call_args.kwargs["asset_id"]
        == output.value["asset_id"]
    )

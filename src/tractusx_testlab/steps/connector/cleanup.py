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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Resource cleanup steps — delete assets, policies, and contract definitions.

Each of the three publishes the status the connector answered its delete with,
under the shared ``status_code`` output, so a teardown asserts on the outcome
the same way whichever resource it tore down.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.shared_models import DeletionOutput
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

#: Status reported when the connector answers a delete with nothing at all —
#: no response object to read a code off, which the SDK reports as a plain None.
_DELETED = 204


# ---------------------------------------------------------------------------
# connector/provider/delete_asset
# ---------------------------------------------------------------------------


class DeleteAssetParams(StepParams):
    """Input contract of ``connector/provider/delete_asset``."""

    asset_id: str = Field(
        default="",
        description="Asset to delete; falls back to the 'asset_id' context variable.",
    )


@step("connector/provider/delete_asset")
class DeleteAssetStep(BaseStep[DeleteAssetParams, DeletionOutput]):
    """Delete an asset from the provider connector."""

    params_model = DeleteAssetParams
    output_model = DeletionOutput

    async def execute(
        self, params: DeleteAssetParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[DeletionOutput]:
        provider = context.dataspace.provider()
        asset_id = params.asset_id or context.get_variable("asset_id")
        url = context.dataspace.provider_endpoint_url("assets", asset_id)

        result = provider.assets.delete(oid=asset_id)
        status = result.status_code if result is not None else _DELETED

        return StepOutput(
            value=DeletionOutput(status_code=status),
            request=HttpRequest(method="DELETE", url=url),
            response=HttpResponse(status_code=status, body=None),
        )


# ---------------------------------------------------------------------------
# connector/provider/delete_policy
# ---------------------------------------------------------------------------


class DeletePolicyParams(StepParams):
    """Input contract of ``connector/provider/delete_policy``."""

    policy_id: str = Field(
        default="",
        description="Policy to delete; falls back to the 'policy_id' context variable.",
    )


@step("connector/provider/delete_policy")
class DeletePolicyStep(BaseStep[DeletePolicyParams, DeletionOutput]):
    """Delete a policy definition from the provider connector."""

    params_model = DeletePolicyParams
    output_model = DeletionOutput

    async def execute(
        self, params: DeletePolicyParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[DeletionOutput]:
        provider = context.dataspace.provider()
        policy_id = params.policy_id or context.get_variable("policy_id")
        url = context.dataspace.provider_endpoint_url("policies", policy_id)

        result = provider.policies.delete(oid=policy_id)
        status = result.status_code if result is not None else _DELETED

        return StepOutput(
            value=DeletionOutput(status_code=status),
            request=HttpRequest(method="DELETE", url=url),
            response=HttpResponse(status_code=status, body=None),
        )


# ---------------------------------------------------------------------------
# connector/provider/delete_contract_definition
# ---------------------------------------------------------------------------


class DeleteContractDefinitionParams(StepParams):
    """Input contract of ``connector/provider/delete_contract_definition``."""

    contract_definition_id: str = Field(
        default="",
        description=(
            "Contract definition to delete; falls back to the "
            "'contract_definition_id' context variable."
        ),
    )


@step("connector/provider/delete_contract_definition")
class DeleteContractDefinitionStep(BaseStep[DeleteContractDefinitionParams, DeletionOutput]):
    """Delete a contract definition from the provider connector.

    Deleting this withdraws the offer from the catalog but leaves the asset and
    policies in place.
    """

    params_model = DeleteContractDefinitionParams
    output_model = DeletionOutput

    async def execute(
        self,
        params: DeleteContractDefinitionParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DeletionOutput]:
        provider = context.dataspace.provider()
        contract_id = params.contract_definition_id or context.get_variable(
            "contract_definition_id"
        )
        url = context.dataspace.provider_endpoint_url("contract_definitions", contract_id)

        result = provider.contract_definitions.delete(oid=contract_id)
        status = result.status_code if result is not None else _DELETED

        return StepOutput(
            value=DeletionOutput(status_code=status),
            request=HttpRequest(method="DELETE", url=url),
            response=HttpResponse(status_code=status, body=None),
        )

    async def cleanup(self, context: StepContext) -> None:
        """No-op cleanup — resource already deleted by execute."""
        # Intentionally empty: the step's execute() already performs the deletion

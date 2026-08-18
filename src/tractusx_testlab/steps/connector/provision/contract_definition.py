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

"""Binding an asset to a policy — ``connector/provider/create_contract_definition``."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator
from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.connector.provision._shared import (
    _as_id,
    _create_or_conflict,
)
from tractusx_testlab.steps.shared_models import FilterExpression
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# connector/provider/create_contract_definition
# ---------------------------------------------------------------------------


#: The EDC property an asset's own ID lives under in a selector criterion.
_ASSET_ID_OPERAND = "https://w3id.org/edc/v0.0.1/ns/id"


class CreateContractDefinitionParams(StepParams):
    """Input contract of ``connector/provider/create_contract_definition``.

    The three ID fields accept either a bare ID or the whole output object of
    the step that created the resource.
    """

    contract_definition_id: str = Field(
        default="", description="Contract definition ID; a fresh UUID is used when omitted."
    )
    contract_policy_id: Any = Field(
        default="",
        description="Policy governing what the consumer may do with the data.",
    )
    access_policy_id: Any = Field(
        default="", description="Policy governing who may see the offer at all."
    )
    asset_id: Any = Field(
        default="",
        description=(
            "Single asset the contract definition offers; ignored when "
            "'asset_selector' is given."
        ),
    )
    asset_selector: list[FilterExpression] = Field(
        default_factory=list,
        description=(
            "Criteria selecting which assets the definition offers, for a "
            "definition that covers more than one. Wins over 'asset_id'."
        ),
    )

    @field_validator("contract_policy_id", "access_policy_id", mode="after")
    @classmethod
    def _unwrap_policy_id(cls, value: Any) -> str:
        return _as_id(value, "policy_id")

    @field_validator("asset_id", mode="after")
    @classmethod
    def _unwrap_asset_id(cls, value: Any) -> str:
        return _as_id(value, "asset_id")

    def assets_selector(self) -> list[dict]:
        """The selector to send, in the camelCase shape the EDC API expects.

        A bare ``asset_id`` is the one-criterion case of a selector, so it is
        expressed as one rather than handled down a second code path.
        """
        if self.asset_selector:
            return [entry.to_sdk() for entry in self.asset_selector]
        return [
            {
                "operandLeft": _ASSET_ID_OPERAND,
                "operator": "=",
                "operandRight": self.asset_id,
            }
        ]


class CreateContractDefinitionOutput(StepPayload):
    """Output contract of ``connector/provider/create_contract_definition``."""

    contract_definition_id: str = Field(
        description="ID of the contract definition that now exists at the provider."
    )


@step("connector/provider/create_contract_definition")
class CreateContractDefinitionStep(
    BaseStep[CreateContractDefinitionParams, CreateContractDefinitionOutput]
):
    """Publish assets by binding them to an access and a contract policy.

    This is the step that makes an asset appear in the provider's catalog; the
    assets and both policies must already exist.  The SDK's own
    ``create_contract`` only ever offers a single asset, so the definition is
    built here and posted through the contract-definition controller.
    """

    params_model = CreateContractDefinitionParams
    output_model = CreateContractDefinitionOutput

    async def execute(
        self,
        params: CreateContractDefinitionParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[CreateContractDefinitionOutput]:
        provider = context.dataspace.provider()
        url = context.dataspace.provider_endpoint_url("contract_definitions")
        definition_id = params.contract_definition_id or str(uuid.uuid4())

        model = ModelFactory.get_contract_definition_model(
            dataspace_version=provider.dataspace_version,
            oid=definition_id,
            access_policy_id=params.access_policy_id,
            contract_policy_id=params.contract_policy_id,
            assets_selector=params.assets_selector(),
        )
        result, http_status = _create_or_conflict(
            _post_definition, controller=provider.contract_definitions, model=model
        )

        return StepOutput(
            value=CreateContractDefinitionOutput(contract_definition_id=definition_id),
            request=HttpRequest(method="POST", url=url, body=json.loads(model.to_data())),
            response=HttpResponse(
                status_code=http_status,
                body={
                    "contract_definition_id": definition_id,
                    **(result if isinstance(result, dict) else {}),
                },
            ),
        )


def _post_definition(controller: Any, model: Any) -> dict:
    """Create a contract definition, raising the way the SDK's helpers do.

    ``_create_or_conflict`` reads a 409 out of the message, so the status has to
    reach it as a ``ValueError`` rather than as a return value.
    """
    response = controller.create(obj=model)
    if response.status_code != 200:
        raise ValueError(
            f"Failed to create contract definition. Status code: {response.status_code}"
        )
    return response.json()

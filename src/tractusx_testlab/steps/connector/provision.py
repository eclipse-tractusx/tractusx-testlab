#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""Asset provisioning steps — reuses SDK ConnectorProviderService."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any, Optional

from pydantic import AliasChoices, Field, field_validator, model_validator

from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import ServiceParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

#: HTTP status the connector answers with when the resource already exists.
_ALREADY_EXISTS = 409


def _as_id(value: Any, *keys: str) -> str:
    """Read an identifier that may arrive as a bare string or a prior step's output.

    Wiring ``${{ steps.create_policy.output }}`` into ``usage_policy_id`` passes
    the whole ``{"policy_id": …}`` object, so the id is picked out of it here
    rather than making every script unwrap it by hand.
    """
    if isinstance(value, dict):
        for key in (*keys, "@id"):
            found = value.get(key)
            if found:
                return str(found)
        return ""
    return str(value) if value else ""


def _create_or_conflict(create, **kwargs) -> tuple[Optional[dict], int]:
    """Run a provider create call, treating a 409 as "already there, carry on"."""
    try:
        result = create(**kwargs)
    except ValueError as exc:
        if "409" in str(exc):
            return None, _ALREADY_EXISTS
        raise
    return result, 200 if result else 500


# ---------------------------------------------------------------------------
# connector/provider/create_asset
# ---------------------------------------------------------------------------


class CreateAssetParams(ServiceParams):
    """Input contract of ``connector/provider/create_asset``.

    Accepts both spellings a script may use: the canonical flat one
    (``asset_id``, ``dct_type``, ``version``) and the CCM one (``name`` plus a
    ``properties`` block carrying ``dct:type`` and ``cx-common:version``).
    """

    asset_id: str = Field(
        default="",
        description="Asset ID; derived from 'name', or a fresh UUID, when omitted.",
    )
    name: str = Field(
        default="",
        description="Human-readable asset name; its slug becomes the asset ID.",
    )
    properties: dict = Field(
        default_factory=dict,
        description="CCM property block; 'dct:type' and 'cx-common:version' are read from it.",
    )
    base_url: str = Field(default="", description="Backend URL the asset proxies to.")
    dct_type: Optional[str] = Field(default=None, description="Asset type as a DCT type IRI.")
    version: str = Field(default="3.0", description="Asset version.")
    semantic_id: Optional[str] = Field(
        default=None, description="Semantic model IRI the asset's data conforms to."
    )
    proxy_params: Optional[dict] = Field(
        default=None, description="Data-plane proxy settings, e.g. path/method forwarding."
    )
    headers: Optional[dict] = Field(
        default=None, description="Headers the data plane sends to the backend."
    )
    private_properties: Optional[dict] = Field(
        default=None, description="Properties kept out of the published catalog."
    )
    context: Optional[Any] = Field(default=None, description="JSON-LD context override.")

    @model_validator(mode="after")
    def _fill_from_ccm_shape(self) -> "CreateAssetParams":
        """Derive the canonical fields the SDK wants from whichever shape arrived."""
        if not self.asset_id:
            self.asset_id = self.name.lower().replace(" ", "-") if self.name else str(uuid.uuid4())
        if self.dct_type is None:
            dct_type = self.properties.get("dct:type")
            if isinstance(dct_type, dict):
                dct_type = dct_type.get("@id", "")
            self.dct_type = dct_type or None
        ccm_version = self.properties.get("cx-common:version")
        if ccm_version and "version" not in self.model_fields_set:
            self.version = ccm_version
        return self


class CreateAssetOutput(StepPayload):
    """Output contract of ``connector/provider/create_asset``."""

    asset_id: str = Field(description="ID of the asset that now exists at the provider.")


@step("connector/provider/create_asset")
class CreateAssetStep(BaseStep[CreateAssetParams, CreateAssetOutput]):
    """Register an asset at the provider connector.

    An asset that already exists is not an error: the connector answers 409 and
    the step reports the ID it would have created, so a script can be re-run
    against a provider it has already provisioned.
    """

    params_model = CreateAssetParams
    output_model = CreateAssetOutput

    async def execute(
        self, params: CreateAssetParams, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput[CreateAssetOutput]:
        service_name = params.service_name()
        provider = context.get_provider_service(service_name)
        url = context.get_provider_endpoint_url("assets", service=service_name)

        result, http_status = _create_or_conflict(
            provider.create_asset,
            asset_id=params.asset_id,
            base_url=params.base_url,
            dct_type=params.dct_type,
            version=params.version,
            semantic_id=params.semantic_id,
            proxy_params=params.proxy_params,
            headers=params.headers,
            private_properties=params.private_properties,
            context=params.context,
        )

        return StepOutput(
            value=CreateAssetOutput(asset_id=params.asset_id),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(
                status_code=http_status,
                body={"asset_id": params.asset_id, **(result if isinstance(result, dict) else {})},
            ),
        )


# ---------------------------------------------------------------------------
# connector/provider/create_policy
# ---------------------------------------------------------------------------


class CreatePolicyParams(ServiceParams):
    """Input contract of ``connector/provider/create_policy``."""

    policy_id: str = Field(
        default="", description="Policy ID; a fresh UUID is used when omitted."
    )
    context: Optional[Any] = Field(default=None, description="JSON-LD context override.")
    permissions: list[dict] = Field(
        default_factory=list, description="ODRL permission rules."
    )
    prohibitions: list[dict] = Field(
        default_factory=list, description="ODRL prohibition rules."
    )
    obligations: list[dict] = Field(
        default_factory=list, description="ODRL obligation rules."
    )


class CreatePolicyOutput(StepPayload):
    """Output contract of ``connector/provider/create_policy``."""

    policy_id: str = Field(description="ID of the policy that now exists at the provider.")


@step("connector/provider/create_policy")
class CreatePolicyStep(BaseStep[CreatePolicyParams, CreatePolicyOutput]):
    """Register an ODRL policy definition at the provider connector.

    As with ``create_asset``, a 409 from the connector is reported as success
    against the existing policy rather than failing the step.
    """

    params_model = CreatePolicyParams
    output_model = CreatePolicyOutput

    async def execute(
        self, params: CreatePolicyParams, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput[CreatePolicyOutput]:
        service_name = params.service_name()
        provider = context.get_provider_service(service_name)
        url = context.get_provider_endpoint_url("policies", service=service_name)
        policy_id = params.policy_id or str(uuid.uuid4())

        rules = {
            "context": params.context,
            "permissions": params.permissions,
            "prohibitions": params.prohibitions,
            "obligations": params.obligations,
        }

        # Build the model to capture the serialized payload for debugging.
        policy_model = ModelFactory.get_policy_model(
            dataspace_version=provider.dataspace_version, oid=policy_id, **rules
        )
        request_body = json.loads(policy_model.to_data())

        result, http_status = _create_or_conflict(
            provider.create_policy, policy_id=policy_id, **rules
        )

        return StepOutput(
            value=CreatePolicyOutput(policy_id=policy_id),
            request=HttpRequest(method="POST", url=url, body=request_body),
            response=HttpResponse(
                status_code=http_status,
                body={"policy_id": policy_id, **(result if isinstance(result, dict) else {})},
            ),
        )


# ---------------------------------------------------------------------------
# connector/provider/create_contract_definition
# ---------------------------------------------------------------------------


class CreateContractDefinitionParams(ServiceParams):
    """Input contract of ``connector/provider/create_contract_definition``.

    The three ID fields accept either a bare ID or the whole output object of
    the step that created the resource.
    """

    contract_id: str = Field(
        default="", description="Contract definition ID; a fresh UUID is used when omitted."
    )
    usage_policy_id: Any = Field(
        default="",
        validation_alias=AliasChoices("usage_policy_id", "contract_policy_id"),
        description="Policy governing what the consumer may do with the data.",
    )
    access_policy_id: Any = Field(
        default="", description="Policy governing who may see the offer at all."
    )
    asset_id: Any = Field(default="", description="Asset the contract definition offers.")

    @field_validator("usage_policy_id", "access_policy_id", mode="after")
    @classmethod
    def _unwrap_policy_id(cls, value: Any) -> str:
        return _as_id(value, "policy_id")

    @field_validator("asset_id", mode="after")
    @classmethod
    def _unwrap_asset_id(cls, value: Any) -> str:
        return _as_id(value, "asset_id")


class CreateContractDefinitionOutput(StepPayload):
    """Output contract of ``connector/provider/create_contract_definition``."""

    contract_def_id: str = Field(
        description="ID of the contract definition that now exists at the provider."
    )


@step("connector/provider/create_contract_definition")
class CreateContractDefinitionStep(
    BaseStep[CreateContractDefinitionParams, CreateContractDefinitionOutput]
):
    """Publish an asset by binding it to an access and a usage policy.

    This is the step that makes an asset appear in the provider's catalog; the
    asset and both policies must already exist.
    """

    params_model = CreateContractDefinitionParams
    output_model = CreateContractDefinitionOutput

    async def execute(
        self,
        params: CreateContractDefinitionParams,
        context: "StepContext",
        definition: StepDefinitionV2,
    ) -> StepOutput[CreateContractDefinitionOutput]:
        service_name = params.service_name()
        provider = context.get_provider_service(service_name)
        url = context.get_provider_endpoint_url("contract_definitions", service=service_name)
        contract_id = params.contract_id or str(uuid.uuid4())

        result, http_status = _create_or_conflict(
            provider.create_contract,
            contract_id=contract_id,
            usage_policy_id=params.usage_policy_id,
            access_policy_id=params.access_policy_id,
            asset_id=params.asset_id,
        )

        return StepOutput(
            value=CreateContractDefinitionOutput(contract_def_id=contract_id),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(
                status_code=http_status,
                body={
                    "contract_def_id": contract_id,
                    **(result if isinstance(result, dict) else {}),
                },
            ),
        )

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
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepParams, StepPayload

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


def _config_object(value: Any, key: str) -> dict:
    """Read a config object that may arrive wrapped in the variable that holds it.

    Wiring ``${{ env.ccm_asset }}`` instead of ``${{ env.ccm_asset.asset }}``
    passes the whole variable, so the object is picked out of it here rather
    than making every script spell out the return key.
    """
    if not isinstance(value, dict):
        return {}
    inner = value.get(key)
    return inner if isinstance(inner, dict) else value


def _iri(value: Any) -> Optional[str]:
    """Read an IRI that may be spelled bare or as a JSON-LD ``{"@id": …}``."""
    if isinstance(value, dict):
        value = value.get("@id")
    return str(value) if value else None


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


class CreateAssetParams(StepParams):
    """Input contract of ``connector/provider/create_asset``.

    The asset arrives as one object rather than as a dozen flat fields: it is
    declared once in the manifest's ``env.variables`` with
    ``uses: config/connector/asset`` and wired in as
    ``asset: ${{ env.<id>.asset }}``.

    Inside that object both spellings are accepted: the canonical flat one
    (``asset_id``, ``dct_type``, ``version``) and the CCM one (``name`` plus a
    ``properties`` block carrying ``dct:type`` and ``cx-common:version``).
    """

    asset_id: str = Field(
        default="",
        description=(
            "Asset ID; read from the asset config, derived from its 'name', or a "
            "fresh UUID, when omitted."
        ),
    )
    asset: dict = Field(
        default_factory=dict,
        description=(
            "The whole asset definition, as declared by a 'config/connector/asset' "
            "manifest variable and referenced as '${{ env.<id>.asset }}'. Carries "
            "'base_url', 'dct_type' or 'properties', 'version', 'semantic_id', "
            "'proxy_params', 'headers', 'private_properties' and an optional '@context'."
        ),
    )

    @field_validator("asset", mode="before")
    @classmethod
    def _unwrap_asset(cls, value: Any) -> Any:
        return _config_object(value, "asset")

    @model_validator(mode="after")
    def _name_the_asset(self) -> "CreateAssetParams":
        """Take the ID from the config, from its name's slug, or invent one."""
        if self.asset_id:
            return self
        name = str(self.asset.get("name") or "")
        self.asset_id = (
            str(self.asset.get("asset_id") or "")
            or name.lower().replace(" ", "-")
            or str(uuid.uuid4())
        )
        return self

    def definition(self) -> dict[str, Any]:
        """The SDK's ``create_asset`` arguments, read out of the asset config."""
        properties = self.asset.get("properties") or {}
        return {
            "base_url": self.asset.get("base_url", ""),
            "dct_type": _iri(self.asset.get("dct_type")) or _iri(properties.get("dct:type")),
            "version": self.asset.get("version") or properties.get("cx-common:version") or "3.0",
            "semantic_id": self.asset.get("semantic_id"),
            "proxy_params": self.asset.get("proxy_params"),
            "headers": self.asset.get("headers"),
            "private_properties": self.asset.get("private_properties"),
            "context": self.asset.get("@context", self.asset.get("context")),
        }


class CreateAssetOutput(StepPayload):
    """Output contract of ``connector/provider/create_asset``."""

    asset_id: str = Field(description="ID of the asset that now exists at the provider.")


@step("connector/provider/create_asset")
class CreateAssetStep(BaseStep[CreateAssetParams, CreateAssetOutput]):
    """Register an asset at the provider connector.

    What the asset *is* is not written into the step: it is configured once in
    the manifest's ``env.variables`` and handed to the step as a single
    ``asset`` input, so the same asset can be reused across tests.

    An asset that already exists is not an error: the connector answers 409 and
    the step reports the ID it would have created, so a script can be re-run
    against a provider it has already provisioned.
    """

    params_model = CreateAssetParams
    output_model = CreateAssetOutput

    async def execute(
        self, params: CreateAssetParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[CreateAssetOutput]:
        provider = context.get_provider_service()
        url = context.get_provider_endpoint_url("assets")

        result, http_status = _create_or_conflict(
            provider.create_asset, asset_id=params.asset_id, **params.definition()
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


class CreatePolicyParams(StepParams):
    """Input contract of ``connector/provider/create_policy``.

    The policy arrives as one object rather than as separate rule lists: it is
    declared once in the manifest's ``env.variables`` with
    ``uses: config/connector/policy`` and wired in as
    ``policy: ${{ env.<id>.policy }}``.
    """

    policy_id: str = Field(
        default="", description="Policy ID; a fresh UUID is used when omitted."
    )
    policy: dict = Field(
        default_factory=dict,
        description=(
            "The whole ODRL policy, as declared by a 'config/connector/policy' "
            "manifest variable and referenced as '${{ env.<id>.policy }}'. Carries "
            "'permissions', 'prohibitions', 'obligations' and an optional '@context'."
        ),
    )

    @field_validator("policy", mode="before")
    @classmethod
    def _unwrap_policy(cls, value: Any) -> Any:
        return _config_object(value, "policy")


class CreatePolicyOutput(StepPayload):
    """Output contract of ``connector/provider/create_policy``."""

    policy_id: str = Field(description="ID of the policy that now exists at the provider.")


@step("connector/provider/create_policy")
class CreatePolicyStep(BaseStep[CreatePolicyParams, CreatePolicyOutput]):
    """Register an ODRL policy definition at the provider connector.

    The rules are not written into the step: the policy is configured once in
    the manifest's ``env.variables`` and handed to the step as a single
    ``policy`` input, so the same policy can be reused across tests.

    As with ``create_asset``, a 409 from the connector is reported as success
    against the existing policy rather than failing the step.
    """

    params_model = CreatePolicyParams
    output_model = CreatePolicyOutput

    async def execute(
        self, params: CreatePolicyParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[CreatePolicyOutput]:
        provider = context.get_provider_service()
        url = context.get_provider_endpoint_url("policies")
        policy_id = params.policy_id or str(uuid.uuid4())

        policy = params.policy
        rules = {
            "context": policy.get("@context", policy.get("context")),
            "permissions": policy.get("permissions", []),
            "prohibitions": policy.get("prohibitions", []),
            "obligations": policy.get("obligations", []),
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


class CreateContractDefinitionParams(StepParams):
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
        definition: StepDefinition,
    ) -> StepOutput[CreateContractDefinitionOutput]:
        provider = context.get_provider_service()
        url = context.get_provider_endpoint_url("contract_definitions")
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

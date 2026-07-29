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
from typing import TYPE_CHECKING

from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


def _normalize_asset_params(params: dict) -> dict:
    """Normalize CCM-style asset params to the canonical format.

    CCM format uses ``name``, ``properties`` with ``dct:type`` and ``cx-common:version``.
    Canonical format uses ``asset_id``, flat ``dct_type``, ``version``.
    """
    normalized = dict(params)

    # asset_id: fall back to name-based slug or auto-generated UUID
    if "asset_id" not in normalized:
        name = normalized.get("name", "")
        normalized["asset_id"] = name.lower().replace(" ", "-") if name else str(uuid.uuid4())

    # Extract dct_type and version from properties if not set directly
    properties = normalized.get("properties", {})
    if properties and "dct_type" not in normalized:
        dct_type_val = properties.get("dct:type")
        if isinstance(dct_type_val, dict):
            dct_type_val = dct_type_val.get("@id", "")
        if dct_type_val:
            normalized["dct_type"] = dct_type_val

    if properties and "version" not in normalized:
        version_val = properties.get("cx-common:version")
        if version_val:
            normalized["version"] = version_val

    return normalized


@step("connector/provider/create_asset", aliases=["create_asset"])
class CreateAssetStep(BaseStep):
    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        service_name = params.get("service") or params.get("connector_service") or None
        provider = context.get_provider_service(service_name)
        url = f"{context.get_provider_base_url()}/v3/assets"
        resolved = _normalize_asset_params(params)
        asset_id = resolved["asset_id"]
        already_exists = False
        try:
            result = provider.create_asset(
                asset_id=asset_id,
                base_url=resolved.get("base_url", ""),
                dct_type=resolved.get("dct_type"),
                version=resolved.get("version", "3.0"),
                semantic_id=resolved.get("semantic_id"),
                proxy_params=resolved.get("proxy_params"),
                headers=resolved.get("headers"),
                private_properties=resolved.get("private_properties"),
                context=resolved.get("context"),
            )
        except ValueError as exc:
            if "409" in str(exc):
                already_exists = True
                result = None
            else:
                raise
        http_status = 409 if already_exists else (200 if result else 500)
        return StepOutput(
            value={"asset_id": asset_id},
            request=HttpRequest(method="POST", url=url, body=resolved),
            response=HttpResponse(
                status_code=http_status,
                body={"asset_id": asset_id, **(result if isinstance(result, dict) else {})},
            ),
        )


@step("connector/provider/create_policy", aliases=["create_policy"])
class CreatePolicyStep(BaseStep):
    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        service_name = params.get("service") or params.get("connector_service") or None
        provider = context.get_provider_service(service_name)
        url = f"{context.get_provider_base_url()}/v3/policydefinitions"

        # CCM format may omit policy_id — auto-generate if missing
        policy_id = params.get("policy_id") or str(uuid.uuid4())

        # Build the model to capture the serialized payload for debugging
        policy_model = ModelFactory.get_policy_model(
            dataspace_version=provider.dataspace_version,
            oid=policy_id,
            context=params.get("context"),
            permissions=params.get("permissions", []),
            prohibitions=params.get("prohibitions", []),
            obligations=params.get("obligations", []),
        )
        request_body = json.loads(policy_model.to_data())

        already_exists = False
        try:
            result = provider.create_policy(
                policy_id=policy_id,
                context=params.get("context"),
                permissions=params.get("permissions", []),
                prohibitions=params.get("prohibitions", []),
                obligations=params.get("obligations", []),
            )
        except ValueError as exc:
            if "409" in str(exc):
                already_exists = True
                result = None
            else:
                raise
        http_status = 409 if already_exists else (200 if result else 500)
        return StepOutput(
            value={"policy_id": policy_id},
            request=HttpRequest(method="POST", url=url, body=request_body),
            response=HttpResponse(
                status_code=http_status,
                body={"policy_id": policy_id, **(result if isinstance(result, dict) else {})},
            ),
        )


@step("connector/provider/create_contract_definition", aliases=["create_contract_definition"])
class CreateContractDefinitionStep(BaseStep):
    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        service_name = params.get("service") or params.get("connector_service") or None
        provider = context.get_provider_service(service_name)
        url = f"{context.get_provider_base_url()}/v3/contractdefinitions"

        # CCM format may omit contract_id — auto-generate if missing
        contract_id = params.get("contract_id") or str(uuid.uuid4())

        # CCM uses contract_policy_id as alias for usage_policy_id
        usage_policy_id = params.get("usage_policy_id") or params.get("contract_policy_id", "")
        # When the resolved value is a dict (from store_in_variable), extract the ID
        if isinstance(usage_policy_id, dict):
            usage_policy_id = usage_policy_id.get("policy_id") or usage_policy_id.get("@id", "")

        # CCM may use asset_selector instead of flat asset_id
        asset_id = params.get("asset_id", "")

        access_policy_id = params.get("access_policy_id", "")
        if isinstance(access_policy_id, dict):
            access_policy_id = access_policy_id.get("policy_id") or access_policy_id.get("@id", "")

        if isinstance(asset_id, dict):
            asset_id = asset_id.get("asset_id") or asset_id.get("@id", "")

        already_exists = False
        try:
            result = provider.create_contract(
                contract_id=contract_id,
                usage_policy_id=usage_policy_id,
                access_policy_id=access_policy_id,
                asset_id=asset_id,
            )
        except ValueError as exc:
            if "409" in str(exc):
                already_exists = True
                result = None
            else:
                raise
        http_status = 409 if already_exists else (200 if result else 500)
        return StepOutput(
            value={"contract_def_id": contract_id},
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(
                status_code=http_status,
                body={"contract_def_id": contract_id, **(result if isinstance(result, dict) else {})},
            ),
        )

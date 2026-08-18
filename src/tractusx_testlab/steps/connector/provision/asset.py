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

"""Registering an asset — ``connector/provider/create_asset`` and its wizard."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.connector.provision._shared import (
    _config_object,
    _create_or_conflict,
    _iri,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


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

    def derived_asset_id(self) -> str:
        """The ID from the config, from its name's slug, or a fresh one."""
        name = str(self.asset.get("name") or "")
        return (
            str(self.asset.get("asset_id") or "")
            or name.lower().replace(" ", "-")
            or str(uuid.uuid4())
        )

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


def _register_asset(
    context: StepContext, asset_id: str, definition: dict[str, Any], request_body: Any
) -> StepOutput[CreateAssetOutput]:
    """Create an asset at the provider and report what happened.

    The one place either asset step reaches the connector: the raw step hands
    over the config it was given, the wizard hands over the config it
    assembled, and both get the same call and the same 409 handling.
    """
    provider = context.dataspace.provider()
    url = context.dataspace.provider_endpoint_url("assets")

    result, http_status = _create_or_conflict(
        provider.create_asset, asset_id=asset_id, **definition
    )

    return StepOutput(
        value=CreateAssetOutput(asset_id=asset_id),
        request=HttpRequest(method="POST", url=url, body=request_body),
        response=HttpResponse(
            status_code=http_status,
            body={"asset_id": asset_id, **(result if isinstance(result, dict) else {})},
        ),
    )


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
        self, params: CreateAssetParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[CreateAssetOutput]:
        return _register_asset(
            context, params.derived_asset_id(), params.definition(), params.model_dump(mode="json")
        )


# ---------------------------------------------------------------------------
# connector/provider/wizard/create_asset
# ---------------------------------------------------------------------------


class WizardCreateAssetParams(StepParams):
    """Input contract of ``connector/provider/wizard/create_asset``.

    The same asset as ``connector/provider/create_asset`` registers, described
    field by field instead of as one document — for a script written by hand or
    by the IDE's form, where there is no reusable asset config to point at.
    """

    asset_id: str = Field(
        default="", description="Asset ID; derived from 'name', or a fresh UUID, when omitted."
    )
    name: str = Field(description="Human-readable asset name.")
    description: str = Field(default="", description="What the asset offers.")
    base_url: str = Field(description="URL of the data source behind the asset.")
    content_type: str = Field(
        default="", description="MIME type of the data, e.g. 'application/json'."
    )
    properties: dict = Field(
        default_factory=dict,
        description=(
            "Further EDC asset properties, e.g. 'dct:type' or 'cx-common:version'."
        ),
    )

    def asset_config(self) -> dict[str, Any]:
        """The asset document these fields describe."""
        properties = {**self.properties}
        for key, value in (
            ("name", self.name),
            ("description", self.description),
            ("contenttype", self.content_type),
        ):
            if value:
                properties.setdefault(key, value)
        return {"name": self.name, "base_url": self.base_url, "properties": properties}


@step("connector/provider/wizard/create_asset")
class WizardCreateAssetStep(BaseStep[WizardCreateAssetParams, CreateAssetOutput]):
    """Register an asset described field by field rather than as a document.

    The guided sibling of ``connector/provider/create_asset``: it assembles the
    asset document from its fields and hands it to the same registration, so
    the two steps cannot drift apart in what they actually create.
    """

    params_model = WizardCreateAssetParams
    output_model = CreateAssetOutput

    async def execute(
        self, params: WizardCreateAssetParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[CreateAssetOutput]:
        assembled = CreateAssetParams(asset=params.asset_config())
        return _register_asset(
            context,
            params.asset_id or assembled.derived_asset_id(),
            assembled.definition(),
            params.model_dump(mode="json"),
        )

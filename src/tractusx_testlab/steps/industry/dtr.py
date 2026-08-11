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

"""Digital Twin Registry steps — reuses SDK AasService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import ConfigDict, Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import NoOutput, StepParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# Shared contract
# ---------------------------------------------------------------------------


class DtrParams(StepParams):
    """What every Digital Twin Registry step accepts.

    ``bpn`` selects the tenant the registry answers for; left out, the AAS
    service uses whatever it was configured with.
    """

    bpn: Optional[str] = Field(
        default=None, description="BPN the registry request is made on behalf of."
    )


class DescriptorPayload(StepPayload):
    """An AAS descriptor as the registry returned it.

    The shape is defined by the AAS specification rather than by testlab, so
    the two keys every descriptor carries are named and the rest of the
    document round-trips untouched.
    """

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(default=None, description="Identifier of the descriptor.")
    id_short: Optional[str] = Field(
        default=None, alias="idShort", description="Short, human-readable name."
    )


def _as_document(result: Any) -> Any:
    """Render an SDK descriptor object as the plain document a script reads."""
    return result.to_dict() if hasattr(result, "to_dict") else result


# ---------------------------------------------------------------------------
# digital-twin/provider/create_shell_descriptor
# ---------------------------------------------------------------------------


class CreateShellDescriptorParams(DtrParams):
    """Input contract of ``digital-twin/provider/create_shell_descriptor``."""

    shell_descriptor: dict = Field(
        description="The AAS shell descriptor document to register."
    )


@step("digital-twin/provider/create_shell_descriptor")
class CreateShellDescriptorStep(BaseStep[CreateShellDescriptorParams, DescriptorPayload]):
    """Create an AAS shell descriptor in the Digital Twin Registry."""

    params_model = CreateShellDescriptorParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: CreateShellDescriptorParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        aas = context.get_aas_service()
        from tractusx_sdk.industry.models.aas.v3.base import ShellDescriptor

        descriptor = ShellDescriptor(**params.shell_descriptor)
        result = aas.create_asset_administration_shell_descriptor(descriptor, bpn=params.bpn)
        url = f"{aas.aas_url}/shell-descriptors"

        body = _as_document(result)
        return StepOutput(
            value=DescriptorPayload.of(body),
            request=HttpRequest(method="POST", url=url, body=params.shell_descriptor),
            response=HttpResponse(status_code=201, body=body),
        )


# ---------------------------------------------------------------------------
# digital-twin/provider/get_shell_descriptor
# ---------------------------------------------------------------------------


class ShellDescriptorRefParams(DtrParams):
    """Names an existing shell descriptor."""

    aas_identifier: str = Field(description="Identifier of the AAS shell descriptor.")


@step("digital-twin/provider/get_shell_descriptor")
class GetShellDescriptorStep(BaseStep[ShellDescriptorRefParams, DescriptorPayload]):
    """Retrieve an AAS shell descriptor by ID."""

    params_model = ShellDescriptorRefParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: ShellDescriptorRefParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        aas = context.get_aas_service()
        result = aas.get_asset_administration_shell_descriptor_by_id(
            params.aas_identifier, bpn=params.bpn
        )
        url = f"{aas.aas_url}/shell-descriptors/{params.aas_identifier}"

        body = _as_document(result)
        return StepOutput(
            value=DescriptorPayload.of(body),
            request=HttpRequest(method="GET", url=url),
            response=HttpResponse(status_code=200, body=body),
        )


# ---------------------------------------------------------------------------
# digital-twin/provider/create_submodel_descriptor
# ---------------------------------------------------------------------------


class CreateSubmodelDescriptorParams(ShellDescriptorRefParams):
    """Input contract of ``digital-twin/provider/create_submodel_descriptor``."""

    submodel_descriptor: dict = Field(
        description="The submodel descriptor document to register under the shell."
    )


@step("digital-twin/provider/create_submodel_descriptor")
class CreateSubmodelDescriptorStep(
    BaseStep[CreateSubmodelDescriptorParams, DescriptorPayload]
):
    """Create a submodel descriptor under an AAS shell."""

    params_model = CreateSubmodelDescriptorParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: CreateSubmodelDescriptorParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        aas = context.get_aas_service()
        from tractusx_sdk.industry.models.aas.v3.base import SubModelDescriptor

        descriptor = SubModelDescriptor(**params.submodel_descriptor)
        result = aas.create_submodel_descriptor(
            params.aas_identifier, descriptor, bpn=params.bpn
        )
        url = f"{aas.aas_url}/shell-descriptors/{params.aas_identifier}/submodel-descriptors"

        body = _as_document(result)
        return StepOutput(
            value=DescriptorPayload.of(body),
            request=HttpRequest(method="POST", url=url, body=params.submodel_descriptor),
            response=HttpResponse(status_code=201, body=body),
        )


# ---------------------------------------------------------------------------
# digital-twin/provider/delete_shell_descriptor
# ---------------------------------------------------------------------------


@step("digital-twin/provider/delete_shell_descriptor")
class DeleteShellDescriptorStep(BaseStep[ShellDescriptorRefParams, NoOutput]):
    """Delete an AAS shell descriptor."""

    params_model = ShellDescriptorRefParams
    output_model = NoOutput

    async def execute(
        self,
        params: ShellDescriptorRefParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[NoOutput]:
        aas = context.get_aas_service()
        result = aas.delete_asset_administration_shell_descriptor(
            params.aas_identifier, bpn=params.bpn
        )
        url = f"{aas.aas_url}/shell-descriptors/{params.aas_identifier}"

        return StepOutput(
            value=NoOutput(None),
            request=HttpRequest(method="DELETE", url=url),
            response=HttpResponse(status_code=204, body=result),
        )

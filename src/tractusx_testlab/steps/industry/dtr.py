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

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("dtr/create_shell_descriptor")
class CreateShellDescriptorStep(BaseStep):
    """Create an AAS shell descriptor in the Digital Twin Registry."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        aas = context.get_aas_service()
        from tractusx_sdk.industry.models.aas.v3.base import ShellDescriptor

        descriptor = ShellDescriptor(**params["shell_descriptor"])
        bpn = params.get("bpn")

        result = aas.create_asset_administration_shell_descriptor(descriptor, bpn=bpn)
        url = f"{aas.aas_url}/shell-descriptors"

        body = result.to_dict() if hasattr(result, "to_dict") else result
        return StepOutput(
            value=body,
            request=HttpRequest(method="POST", url=url, body=params["shell_descriptor"]),
            response=HttpResponse(status_code=201, body=body),
        )


@step("dtr/get_shell_descriptor")
class GetShellDescriptorStep(BaseStep):
    """Retrieve an AAS shell descriptor by ID."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        aas = context.get_aas_service()
        aas_id = params["aas_identifier"]
        bpn = params.get("bpn")

        result = aas.get_asset_administration_shell_descriptor_by_id(aas_id, bpn=bpn)
        url = f"{aas.aas_url}/shell-descriptors/{aas_id}"

        body = result.to_dict() if hasattr(result, "to_dict") else result
        return StepOutput(
            value=body,
            request=HttpRequest(method="GET", url=url),
            response=HttpResponse(status_code=200, body=body),
        )


@step("dtr/create_submodel_descriptor")
class CreateSubmodelDescriptorStep(BaseStep):
    """Create a submodel descriptor under an AAS shell."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        aas = context.get_aas_service()
        from tractusx_sdk.industry.models.aas.v3.base import SubModelDescriptor

        aas_id = params["aas_identifier"]
        descriptor = SubModelDescriptor(**params["submodel_descriptor"])
        bpn = params.get("bpn")

        result = aas.create_submodel_descriptor(aas_id, descriptor, bpn=bpn)
        url = f"{aas.aas_url}/shell-descriptors/{aas_id}/submodel-descriptors"

        body = result.to_dict() if hasattr(result, "to_dict") else result
        return StepOutput(
            value=body,
            request=HttpRequest(method="POST", url=url, body=params["submodel_descriptor"]),
            response=HttpResponse(status_code=201, body=body),
        )


@step("dtr/delete_shell_descriptor")
class DeleteShellDescriptorStep(BaseStep):
    """Delete an AAS shell descriptor."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        aas = context.get_aas_service()
        aas_id = params["aas_identifier"]
        bpn = params.get("bpn")

        result = aas.delete_asset_administration_shell_descriptor(aas_id, bpn=bpn)
        url = f"{aas.aas_url}/shell-descriptors/{aas_id}"

        return StepOutput(
            value=result,
            request=HttpRequest(method="DELETE", url=url),
            response=HttpResponse(status_code=204, body=result),
        )

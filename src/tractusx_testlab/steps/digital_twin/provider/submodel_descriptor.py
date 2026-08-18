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


"""Submodel descriptors, which live under a shell descriptor.

A submodel descriptor says where a submodel's data can be fetched and under
which semantic id. It is addressed through the shell that holds it, which is
why :class:`ShellDescriptorRefParams` comes from
:mod:`~tractusx_testlab.steps.digital_twin.provider.shell`.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.registry_models import (
    DescriptorPayload,
    _as_document,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


from tractusx_testlab.steps.digital_twin.provider.shell import ShellDescriptorRefParams

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
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        return await _register_submodel(
            context, params.aas_identifier, params.submodel_descriptor, params.bpn
        )


async def _register_submodel(
    context: StepContext,
    aas_identifier: str,
    submodel_descriptor: dict,
    bpn: str | None,
) -> StepOutput[DescriptorPayload]:
    """Attach a submodel descriptor, whether it was written out or assembled."""
    from tractusx_sdk.industry.models.aas.v3.base import SubModelDescriptor

    aas = context.dataspace.registry()
    result = await sdk_call.run(aas.create_submodel_descriptor,
        aas_identifier, SubModelDescriptor(**submodel_descriptor), bpn=bpn
    )
    url = f"{aas.aas_url}/shell-descriptors/{aas_identifier}/submodel-descriptors"

    body = _as_document(result)
    return StepOutput(
        value=DescriptorPayload.of(body),
        request=HttpRequest(method="POST", url=url, body=submodel_descriptor),
        response=HttpResponse(status_code=201, body=body),
    )


# ---------------------------------------------------------------------------
# digital-twin/provider/wizard/create_submodel_descriptor
# ---------------------------------------------------------------------------

#: Endpoint values CX-0002 fixes outright. They are written, never asked for:
#: the standard admits no other value, so an input would only invite a wrong one.
_ENDPOINT_PROTOCOL = "HTTP"
_ENDPOINT_PROTOCOL_VERSION = "1.1"
_SUBMODEL_SUBPROTOCOL = "DSP"
_SUBPROTOCOL_BODY_ENCODING = "plain"


class WizardCreateSubmodelDescriptorParams(ShellDescriptorRefParams):
    """Input contract of ``digital-twin/provider/wizard/create_submodel_descriptor``.

    A submodel descriptor is mostly boilerplate around a few facts: what the
    submodel is called, which aspect model it follows, where its data can be
    fetched, and — because the data is fetched through a dataspace and not from
    the bare URL — which asset it is offered as and which control plane that
    offer lives on. This step takes those and writes the rest.

    Of the endpoint's keys only ``interface`` is asked for, because it is the
    only one CX-0002 leaves a choice in; the rest are fixed by the standard and
    written from the constants above.
    """

    id: str = Field(
        default="", description="Submodel identifier; a fresh URN UUID when omitted."
    )
    id_short: str = Field(
        default="",
        description=(
            "Short, human-readable name for the submodel. CX-0002 does not "
            "require one, so an omitted name is left out of the descriptor."
        ),
    )
    semantic_id: str = Field(description="URN of the aspect model the submodel follows.")
    href: str = Field(
        description=(
            "URL the submodel's data is served from, written to the endpoint's "
            "'href'. Give the bare data URL: the '$'-suffix the chosen "
            "interface calls for is this step's to write."
        )
    )
    asset_id: str = Field(
        description="Asset ID the submodel is offered as — the subprotocol body's 'id'."
    )
    dsp_endpoint: str = Field(
        description=(
            "DSP URL of the provider control plane the asset is negotiated "
            "through — the subprotocol body's 'dspEndpoint'."
        )
    )
    interface: str = Field(
        default="SUBMODEL-3.0",
        description=(
            "AAS interface the endpoint implements — SUBMODEL-3.X, or "
            "SUBMODEL-VALUE-3.X when the href is directly callable as given."
        ),
    )
    def endpoint_href(self) -> str:
        """The href the chosen interface asks for (CX-0002).

        ``SUBMODEL-3.X`` names an endpoint the consumer appends ``$``-suffixes
        to, so the href must not carry one; ``SUBMODEL-VALUE-3.X`` promises a
        directly callable href, so the step appends ``/submodel/$value`` —
        just ``/$value`` when the URL already ends in ``/submodel``, and
        nothing when it already carries a ``$``-segment. Either way the author
        gives the URL they have and the step writes the conformant spelling.
        """
        url = self.href.rstrip("/")
        tail = url.rsplit("/", 1)[-1]
        if self.interface.startswith("SUBMODEL-VALUE"):
            if tail.startswith("$"):
                return url
            return f"{url}/$value" if tail == "submodel" else f"{url}/submodel/$value"
        return url.rsplit("/", 1)[0] if tail.startswith("$") else self.href

    def submodel_document(self) -> dict:
        """The AAS submodel descriptor these fields describe."""
        document = {
            "id": self.id or f"urn:uuid:{uuid.uuid4()}",
            "semanticId": {
                "type": "ExternalReference",
                "keys": [{"type": "GlobalReference", "value": self.semantic_id}],
            },
            "endpoints": [
                {
                    "interface": self.interface,
                    "protocolInformation": {
                        "href": self.endpoint_href(),
                        "endpointProtocol": _ENDPOINT_PROTOCOL,
                        "endpointProtocolVersion": [_ENDPOINT_PROTOCOL_VERSION],
                        "subprotocol": _SUBMODEL_SUBPROTOCOL,
                        "subprotocolBody": (
                            f"id={self.asset_id};dspEndpoint={self.dsp_endpoint}"
                        ),
                        "subprotocolBodyEncoding": _SUBPROTOCOL_BODY_ENCODING,
                    },
                }
            ],
        }
        if self.id_short:
            document["idShort"] = self.id_short
        return document


@step("digital-twin/provider/wizard/create_submodel_descriptor")
class WizardCreateSubmodelDescriptorStep(
    BaseStep[WizardCreateSubmodelDescriptorParams, DescriptorPayload]
):
    """Attach a submodel descriptor described field by field.

    The guided sibling of ``digital-twin/provider/create_submodel_descriptor``,
    registering through the same call.
    """

    params_model = WizardCreateSubmodelDescriptorParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: WizardCreateSubmodelDescriptorParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        return await _register_submodel(
            context, params.aas_identifier, params.submodel_document(), params.bpn
        )

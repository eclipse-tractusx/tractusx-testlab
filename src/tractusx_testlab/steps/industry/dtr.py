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

"""Digital Twin Registry steps.

The ``digital-twin/provider/*`` steps talk to the registry the run was seeded
with, through the SDK's ``AasService``.  The consumer-side lookup does not: it
reaches a *counterparty's* registry through an EDC data plane, so it takes the
data-plane URL and EDR token a transfer produced and speaks HTTP directly.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field

from tractusx_sdk.dataspace.tools import encode_as_base64_url_safe
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import HttpTransportParams, NoOutput, StepParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import DATA_ADDRESS, EDR_TOKEN

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


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
    # The AAS API spells it ``idShort``; scripts read ``id_short`` and nothing
    # else, so the camelCase form is accepted on the way in and never written
    # on the way out.
    id_short: Optional[str] = Field(
        default=None,
        validation_alias="idShort",
        description="Short, human-readable name.",
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


# ---------------------------------------------------------------------------
# digital-twin-registry/consumer/dataplane/lookup_shell
# ---------------------------------------------------------------------------


class SpecificAssetId(BaseModel):
    """One ``specificAssetIds`` criterion a shell is searched by.

    Defined by the AAS specification rather than by testlab, so the two keys a
    lookup always sends are named and anything else — ``externalSubjectId`` for
    a criterion visible to one partner only — round-trips untouched.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Name of the asset identifier, e.g. 'partInstanceId'.")
    value: str = Field(description="Value that identifier must have.")


class ShellLookupParams(HttpTransportParams):
    """Input contract of ``digital-twin-registry/consumer/dataplane/lookup_shell``.

    The registry is a counterparty's, so it is reached the way any negotiated
    endpoint is: through the data-plane URL and EDR token a transfer published.
    """

    specific_asset_ids: list[SpecificAssetId] = Field(
        min_length=1,
        description="Criteria the shell must match; all of them have to.",
    )
    dataplane_url: str = Field(
        default="",
        description=(
            "Data-plane URL of the counterparty's registry; falls back to the "
            "'data_address' context variable."
        ),
    )
    edr_token: str = Field(
        default="",
        description="EDR authorization token; falls back to the 'edr_token' context variable.",
    )

    def asset_id_query(self) -> list[str]:
        """The criteria as the ``assetIds`` query values the AAS API expects.

        Each criterion travels as its own base64url-encoded JSON object — that
        is the AAS v3 encoding, not a testlab convention.
        """
        return [
            encode_as_base64_url_safe(json.dumps(entry.model_dump(exclude_none=True)))
            for entry in self.specific_asset_ids
        ]


class ShellLookupOutput(StepPayload):
    """Output contract of ``digital-twin-registry/consumer/dataplane/lookup_shell``."""

    shell_ids: list[str] = Field(
        default_factory=list, description="Identifiers of the shells that matched."
    )
    shell_descriptors: list[dict] = Field(
        default_factory=list,
        description="The descriptor document of each matching shell.",
    )


@step("digital-twin-registry/consumer/dataplane/lookup_shell")
class ShellLookupStep(BaseStep[ShellLookupParams, ShellLookupOutput]):
    """Search a counterparty's registry for shells matching specific asset IDs.

    This is the consumer's half of the DTR contract, and it is a different
    thing from ``digital-twin/provider/get_shell_descriptor``: that one reads a
    known shell out of the registry the run was seeded with, this one searches
    somebody else's over a negotiated data plane.  The lookup returns
    identifiers, so each one is then read back as a descriptor — a script that
    only needs the identifiers reads ``shell_ids`` and ignores the rest.
    """

    params_model = ShellLookupParams
    output_model = ShellLookupOutput

    async def execute(
        self,
        params: ShellLookupParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[ShellLookupOutput]:
        base = (params.dataplane_url or context.get_variable(DATA_ADDRESS, "")).rstrip("/")
        token = params.edr_token or context.get_variable(EDR_TOKEN, "")
        headers = {"Authorization": token, **params.headers}
        timeout = params.timeout_or(context.config.default_timeout_s)

        url = f"{base}/lookup/shells"
        query = {"assetIds": params.asset_id_query()}
        response = requests.get(url, params=query, headers=headers, timeout=timeout)

        shell_ids = _shell_ids(response)
        descriptors = [
            document
            for shell_id in shell_ids
            if (document := _shell_descriptor(base, shell_id, headers, timeout)) is not None
        ]

        return StepOutput(
            value=ShellLookupOutput(shell_ids=shell_ids, shell_descriptors=descriptors),
            request=HttpRequest(method="GET", url=url, headers=headers, body=query),
            response=HttpResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body={"shell_ids": shell_ids, "shell_descriptors": descriptors},
            ),
        )


def _shell_ids(response: Any) -> list[str]:
    """Read the identifiers out of a lookup answer, in either shape it comes in.

    AAS v3 pages its collections as ``{"paging_metadata": …, "result": […]}``;
    older registries answer with the bare list.
    """
    if response.status_code != 200:
        logger.error("Shell lookup failed with status %s", response.status_code)
        return []
    try:
        body = response.json()
    except ValueError:
        logger.error("Shell lookup answered with a body that is not JSON")
        return []
    found = body.get("result", []) if isinstance(body, dict) else body
    return [str(entry) for entry in found or []]


def _shell_descriptor(
    base: str, shell_id: str, headers: dict, timeout: float
) -> Optional[dict]:
    """Read one shell descriptor by identifier, or ``None`` when it cannot be read.

    A shell the lookup named but the registry will not hand over is reported by
    its absence from ``shell_descriptors``; the identifier is still in
    ``shell_ids``, so a script can assert on the difference.
    """
    url = f"{base}/shell-descriptors/{encode_as_base64_url_safe(shell_id)}"
    response = requests.get(url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        logger.warning("Shell descriptor %s could not be read (%s)", shell_id, response.status_code)
        return None
    try:
        return response.json()
    except ValueError:
        return None

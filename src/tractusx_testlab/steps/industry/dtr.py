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
with, through the SDK's ``AasService``.  The consumer-side steps do not: they
reach a *counterparty's* registry through an EDC data plane, so they take the
data-plane URL and EDR token a transfer produced and speak HTTP directly.
Both sides read the same registry API — a consumer step is the provider
operation re-addressed through the data plane, not a different operation.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field

from tractusx_sdk.dataspace.tools import encode_as_base64_url_safe
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import (
    DeletionOutput,
    HttpTransportParams,
    StepParams,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import DATAPLANE_URL, EDR_TOKEN

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
        return _register_shell(context, params.shell_descriptor, params.bpn)


def _register_shell(
    context: "StepContext", shell_descriptor: dict, bpn: Optional[str]
) -> StepOutput[DescriptorPayload]:
    """Register a shell descriptor, whether it was written out or assembled.

    The one place either shell-creation step reaches the registry, so the two
    cannot drift apart in what they register.
    """
    from tractusx_sdk.industry.models.aas.v3.base import ShellDescriptor

    aas = context.get_aas_service()
    result = aas.create_asset_administration_shell_descriptor(
        ShellDescriptor(**shell_descriptor), bpn=bpn
    )
    url = f"{aas.aas_url}/shell-descriptors"

    body = _as_document(result)
    return StepOutput(
        value=DescriptorPayload.of(body),
        request=HttpRequest(method="POST", url=url, body=shell_descriptor),
        response=HttpResponse(status_code=201, body=body),
    )


# ---------------------------------------------------------------------------
# digital-twin/provider/wizard/create_shell_descriptor
# ---------------------------------------------------------------------------


class WizardCreateShellDescriptorParams(DtrParams):
    """Input contract of ``digital-twin/provider/wizard/create_shell_descriptor``.

    The same shell as ``digital-twin/provider/create_shell_descriptor``
    registers, described field by field instead of as one AAS document.
    """

    id: str = Field(
        default="", description="Shell identifier; a fresh URN UUID when omitted."
    )
    id_short: str = Field(description="Short, human-readable name for the shell.")
    global_asset_id: str = Field(
        default="", description="Global asset ID the twin represents, as a URN."
    )
    specific_asset_ids: list[dict] = Field(
        default_factory=list,
        description="Identifiers the shell can be looked up by, as {name, value} pairs.",
    )
    submodel_descriptors: list[dict] = Field(
        default_factory=list,
        description="Submodel descriptors to attach as the shell is created.",
    )

    def shell_document(self) -> dict:
        """The AAS shell descriptor these fields describe."""
        document: dict[str, Any] = {
            "id": self.id or f"urn:uuid:{uuid.uuid4()}",
            "idShort": self.id_short,
        }
        if self.global_asset_id:
            document["globalAssetId"] = self.global_asset_id
        if self.specific_asset_ids:
            document["specificAssetIds"] = self.specific_asset_ids
        if self.submodel_descriptors:
            document["submodelDescriptors"] = self.submodel_descriptors
        return document


@step("digital-twin/provider/wizard/create_shell_descriptor")
class WizardCreateShellDescriptorStep(
    BaseStep[WizardCreateShellDescriptorParams, DescriptorPayload]
):
    """Register a shell descriptor described field by field.

    The guided sibling of ``digital-twin/provider/create_shell_descriptor``,
    registering through the same call.
    """

    params_model = WizardCreateShellDescriptorParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: WizardCreateShellDescriptorParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        return _register_shell(context, params.shell_document(), params.bpn)


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
        return _register_submodel(
            context, params.aas_identifier, params.submodel_descriptor, params.bpn
        )


def _register_submodel(
    context: "StepContext",
    aas_identifier: str,
    submodel_descriptor: dict,
    bpn: Optional[str],
) -> StepOutput[DescriptorPayload]:
    """Attach a submodel descriptor, whether it was written out or assembled."""
    from tractusx_sdk.industry.models.aas.v3.base import SubModelDescriptor

    aas = context.get_aas_service()
    result = aas.create_submodel_descriptor(
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
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        return _register_submodel(
            context, params.aas_identifier, params.submodel_document(), params.bpn
        )


# ---------------------------------------------------------------------------
# digital-twin/provider/delete_shell_descriptor
# ---------------------------------------------------------------------------


#: Status a registry answers a delete it accepted with.  The SDK collapses that
#: answer to ``None``, so the code is written here rather than read back.
_DELETED = 204

#: Status reported when the registry refused the delete but named no code of its
#: own.  400 says the delete did not happen without inventing a reason.
_DELETE_REFUSED = 400


def _delete_status(result: Any) -> int:
    """The status a registry answered a delete with, as far as the SDK reports it.

    ``delete_asset_administration_shell_descriptor`` returns ``None`` when the
    registry accepted the delete and an AAS ``Result`` when it refused, so the
    code of a refusal has to be read out of the refusal document: AAS carries it
    in each message's ``code``.  A registry that puts something else there, or
    sends no message at all, reads as a plain refusal.
    """
    if result is None:
        return _DELETED
    for message in getattr(result, "messages", None) or []:
        code = str(getattr(message, "code", "") or "")
        if code.isdigit():
            return int(code)
    return _DELETE_REFUSED


@step("digital-twin/provider/delete_shell_descriptor")
class DeleteShellDescriptorStep(BaseStep[ShellDescriptorRefParams, DeletionOutput]):
    """Delete an AAS shell descriptor.

    The status the registry answered with is published as ``status_code``, so a
    teardown can assert that the twin was really there (204) rather than already
    gone (404).
    """

    params_model = ShellDescriptorRefParams
    output_model = DeletionOutput

    async def execute(
        self,
        params: ShellDescriptorRefParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[DeletionOutput]:
        aas = context.get_aas_service()
        result = aas.delete_asset_administration_shell_descriptor(
            params.aas_identifier, bpn=params.bpn
        )
        url = f"{aas.aas_url}/shell-descriptors/{params.aas_identifier}"
        status = _delete_status(result)

        return StepOutput(
            value=DeletionOutput(status_code=status),
            request=HttpRequest(method="DELETE", url=url),
            response=HttpResponse(status_code=status, body=result),
        )


# ---------------------------------------------------------------------------
# The consumer-side transport
# ---------------------------------------------------------------------------


class DataplaneParams(HttpTransportParams):
    """How every consumer-side registry step reaches the counterparty.

    The registry is a counterparty's, so it is reached the way any negotiated
    endpoint is: through the data-plane URL and EDR token a transfer published.
    """

    dataplane_url: str = Field(
        default="",
        description=(
            "Data-plane URL of the counterparty's registry; falls back to the "
            "'dataplane_url' context variable."
        ),
    )
    edr_token: str = Field(
        default="",
        description="EDR authorization token; falls back to the 'edr_token' context variable.",
    )

    def transport(self, context: "StepContext") -> tuple[str, dict[str, str], float]:
        """The (base URL, headers, timeout) this step's requests travel with."""
        base = (self.dataplane_url or context.get_variable(DATAPLANE_URL, "")).rstrip("/")
        token = self.edr_token or context.get_variable(EDR_TOKEN, "")
        headers = {"Authorization": token, **self.headers}
        return base, headers, self.timeout_or(context.config.default_timeout_s)


class PagedDataplaneParams(DataplaneParams):
    """A consumer-side registry read whose answer the registry may page.

    The AAS v3 paging controls, declared once so every collection read offers
    them under the same two names.
    """

    limit: Optional[int] = Field(
        default=None,
        gt=0,
        description=(
            "Maximum number of entries the registry may return in one page; "
            "its own default applies when omitted."
        ),
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Cursor a previous page returned, to read the page after it.",
    )

    def page_query(self) -> dict:
        """The paging parameters, with the ones the script left out omitted."""
        query: dict = {}
        if self.limit is not None:
            query["limit"] = self.limit
        if self.cursor is not None:
            query["cursor"] = self.cursor
        return query


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


class ShellLookupParams(DataplaneParams):
    """Input contract of ``digital-twin-registry/consumer/dataplane/lookup_shell``."""

    specific_asset_ids: list[SpecificAssetId] = Field(
        min_length=1,
        description="Criteria the shell must match; all of them have to.",
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
    """Shells a consumer-side registry read returned.

    The one output shape of every consumer step that answers with a collection,
    so a script reads ``shell_ids`` and ``shell_descriptors`` the same way
    whether the shells were searched for or listed.
    """

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
        base, headers, timeout = params.transport(context)

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


# ---------------------------------------------------------------------------
# digital-twin-registry/consumer/dataplane/lookup_shells_by_asset_link
# ---------------------------------------------------------------------------


class ShellLookupByAssetLinkParams(PagedDataplaneParams):
    """Input contract of ``digital-twin-registry/consumer/dataplane/lookup_shells_by_asset_link``."""

    specific_asset_ids: list[SpecificAssetId] = Field(
        min_length=1,
        description="Criteria the shell must match; all of them have to.",
    )

    def asset_link_body(self) -> list[dict]:
        """The criteria as the JSON body ``POST /lookup/shellsByAssetLink`` expects.

        The whole point of this endpoint over ``GET /lookup/shells``: the
        criteria travel as a plain JSON array in the body, so they are neither
        base64url-encoded nor bounded by a URL length limit.
        """
        return [entry.model_dump(exclude_none=True) for entry in self.specific_asset_ids]

    def page_query(self) -> dict:
        """The paging parameters, with the ones the script left out omitted."""
        query: dict = {}
        if self.limit is not None:
            query["limit"] = self.limit
        if self.cursor is not None:
            query["cursor"] = self.cursor
        return query


class ShellLookupPageOutput(ShellLookupOutput):
    """One page of a shell lookup.

    The collection shape every consumer-side read answers with, plus the cursor
    a paged registry hands back, so a script can ask for the next page without
    reaching into the raw response.
    """

    cursor: Optional[str] = Field(
        default=None,
        description="Cursor of the next page, or null when this was the last one.",
    )


@step("digital-twin-registry/consumer/dataplane/lookup_shells_by_asset_link")
class ShellLookupByAssetLinkStep(
    BaseStep[ShellLookupByAssetLinkParams, ShellLookupPageOutput]
):
    """Search a counterparty's registry through ``POST /lookup/shellsByAssetLink``.

    The same search ``digital-twin-registry/consumer/dataplane/lookup_shell``
    performs, addressed to the endpoint that carries the criteria in the request
    body instead of in base64url-encoded ``assetIds`` query values.  That is what
    it is for: a query string has a length limit and a body does not, so a lookup
    with many criteria — or with long ``externalSubjectId`` scopes on them — is
    the case ``GET /lookup/shells`` cannot serve.  The answer is paged, so the
    cursor is returned alongside the identifiers and their descriptors.
    """

    params_model = ShellLookupByAssetLinkParams
    output_model = ShellLookupPageOutput

    async def execute(
        self,
        params: ShellLookupByAssetLinkParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[ShellLookupPageOutput]:
        base, headers, timeout = params.transport(context)

        url = f"{base}/lookup/shellsByAssetLink"
        body = params.asset_link_body()
        query = params.page_query()
        response = requests.post(
            url,
            params=query,
            json=body,
            headers={"Content-Type": "application/json", **headers},
            timeout=timeout,
        )

        shell_ids = _shell_ids(response)
        cursor = _next_cursor(response)
        descriptors = [
            document
            for shell_id in shell_ids
            if (document := _shell_descriptor(base, shell_id, headers, timeout)) is not None
        ]

        return StepOutput(
            value=ShellLookupPageOutput(
                shell_ids=shell_ids, shell_descriptors=descriptors, cursor=cursor
            ),
            request=HttpRequest(method="POST", url=url, headers=headers, body=body),
            response=HttpResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body={
                    "shell_ids": shell_ids,
                    "shell_descriptors": descriptors,
                    "cursor": cursor,
                },
            ),
        )


def _result_page(response: Any, what: str) -> list:
    """Read the entries out of a collection answer, in either shape it comes in.

    AAS v3 pages its collections as ``{"paging_metadata": …, "result": […]}``;
    older registries answer with the bare list.
    """
    if response.status_code != 200:
        logger.error("%s failed with status %s", what, response.status_code)
        return []
    try:
        body = response.json()
    except ValueError:
        logger.error("%s answered with a body that is not JSON", what)
        return []
    return list((body.get("result", []) if isinstance(body, dict) else body) or [])


def _shell_ids(response: Any) -> list[str]:
    """Read the identifiers out of a lookup answer."""
    return [str(entry) for entry in _result_page(response, "Shell lookup")]


def _next_cursor(response: Any) -> Optional[str]:
    """Read the next-page cursor out of a paged answer, when there is one.

    Absent from a registry that answered with the bare list, and absent from the
    last page of one that pages — both read as ``None``.
    """
    if response.status_code != 200:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    cursor = (body.get("paging_metadata") or {}).get("cursor")
    return str(cursor) if cursor else None


def _get_shell_descriptor(
    base: str, shell_id: str, headers: dict, timeout: float
) -> tuple[str, Any]:
    """GET one shell descriptor by identifier, base64url-encoded as the AAS API expects.

    The one place any consumer-side step reads a descriptor, whether a script
    asked for it by identifier or a lookup surfaced it.
    """
    url = f"{base}/shell-descriptors/{encode_as_base64_url_safe(shell_id)}"
    return url, requests.get(url, headers=headers, timeout=timeout)


def _shell_descriptor(
    base: str, shell_id: str, headers: dict, timeout: float
) -> Optional[dict]:
    """Read one shell descriptor by identifier, or ``None`` when it cannot be read.

    A shell the lookup named but the registry will not hand over is reported by
    its absence from ``shell_descriptors``; the identifier is still in
    ``shell_ids``, so a script can assert on the difference.
    """
    _, response = _get_shell_descriptor(base, shell_id, headers, timeout)
    if response.status_code != 200:
        logger.warning("Shell descriptor %s could not be read (%s)", shell_id, response.status_code)
        return None
    try:
        return response.json()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# digital-twin-registry/consumer/dataplane/get_shell_descriptors
# ---------------------------------------------------------------------------


@step("digital-twin-registry/consumer/dataplane/get_shell_descriptors")
class DataplaneGetShellDescriptorsStep(BaseStep[PagedDataplaneParams, ShellLookupPageOutput]):
    """List a counterparty's shell descriptors over a negotiated data plane.

    The consumer-side reading of the registry's ``GET /shell-descriptors`` —
    the same collection a provider populates with
    ``digital-twin/provider/create_shell_descriptor``, reached through the
    data-plane URL and EDR token a transfer published.  The registry answers
    with whatever the counterparty's access rules let this consumer see; the
    answer is paged, so the cursor is returned alongside the descriptors.
    """

    params_model = PagedDataplaneParams
    output_model = ShellLookupPageOutput

    async def execute(
        self,
        params: PagedDataplaneParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[ShellLookupPageOutput]:
        base, headers, timeout = params.transport(context)

        url = f"{base}/shell-descriptors"
        response = requests.get(
            url, params=params.page_query(), headers=headers, timeout=timeout
        )

        descriptors = [
            entry
            for entry in _result_page(response, "Shell descriptor listing")
            if isinstance(entry, dict)
        ]
        shell_ids = [str(entry["id"]) for entry in descriptors if "id" in entry]
        cursor = _next_cursor(response)

        return StepOutput(
            value=ShellLookupPageOutput(
                shell_ids=shell_ids, shell_descriptors=descriptors, cursor=cursor
            ),
            request=HttpRequest(method="GET", url=url, headers=headers),
            response=HttpResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body={
                    "shell_ids": shell_ids,
                    "shell_descriptors": descriptors,
                    "cursor": cursor,
                },
            ),
        )


# ---------------------------------------------------------------------------
# digital-twin-registry/consumer/dataplane/get_shell_descriptor
# ---------------------------------------------------------------------------


class DataplaneShellDescriptorRefParams(DataplaneParams):
    """Names a shell descriptor in a counterparty's registry."""

    aas_identifier: str = Field(description="Identifier of the AAS shell descriptor.")


@step("digital-twin-registry/consumer/dataplane/get_shell_descriptor")
class DataplaneGetShellDescriptorStep(
    BaseStep[DataplaneShellDescriptorRefParams, DescriptorPayload]
):
    """Retrieve one of a counterparty's shell descriptors by ID.

    The consumer-side reading of
    ``digital-twin/provider/get_shell_descriptor``: the same registry document,
    reached through the data-plane URL and EDR token a transfer published
    instead of the registry the run was seeded with.  A registry that answers
    anything but 200 yields an empty descriptor; the status code stays on the
    response for a script to assert on.
    """

    params_model = DataplaneShellDescriptorRefParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: DataplaneShellDescriptorRefParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        base, headers, timeout = params.transport(context)
        url, response = _get_shell_descriptor(
            base, params.aas_identifier, headers, timeout
        )

        if response.status_code == 200:
            try:
                body = response.json()
            except ValueError:
                body = {}
        else:
            logger.error(
                "Shell descriptor %s could not be read (%s)",
                params.aas_identifier,
                response.status_code,
            )
            body = {}

        return StepOutput(
            value=DescriptorPayload.of(body),
            request=HttpRequest(method="GET", url=url, headers=headers),
            response=HttpResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=body,
            ),
        )

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


"""Consumer-side Digital Twin Registry steps — ``digital-twin-registry/consumer/*``.

Reading a counterpart's registry across a data plane: the URL and token come
from an EDR the connector negotiated, not from a service the engine holds. The
provider-side steps are in
:mod:`tractusx_testlab.steps.digital_twin.provider`.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from tractusx_sdk.dataspace.tools import encode_as_base64_url_safe

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.registry_reading import (
    _get_shell_descriptor,
    _next_cursor,
    _result_page,
    _shell_descriptor,
    _shell_ids,
)
from tractusx_testlab.steps.shared_models import (
    HttpTransportParams,
    StepParams,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload
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

    bpn: str | None = Field(
        default=None, description="BPN the registry request is made on behalf of."
    )


class DescriptorPayload(StepPayload):
    """An AAS descriptor as the registry returned it.

    The shape is defined by the AAS specification rather than by testlab, so
    the two keys every descriptor carries are named and the rest of the
    document round-trips untouched.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = Field(default=None, description="Identifier of the descriptor.")
    # The AAS API spells it ``idShort``; scripts read ``id_short`` and nothing
    # else, so the camelCase form is accepted on the way in and never written
    # on the way out.
    id_short: str | None = Field(
        default=None,
        validation_alias="idShort",
        description="Short, human-readable name.",
    )


def _as_document(result: Any) -> Any:
    """Render an SDK descriptor object as the plain document a script reads."""
    return result.to_dict() if hasattr(result, "to_dict") else result


class SpecificAssetId(BaseModel):
    """One ``specificAssetIds`` criterion a shell is searched by.

    Defined by the AAS specification rather than by testlab, so the two keys a
    lookup always sends are named and anything else — ``externalSubjectId`` for
    a criterion visible to one partner only — round-trips untouched.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Name of the asset identifier, e.g. 'partInstanceId'.")
    value: str = Field(description="Value that identifier must have.")


def _asset_ids_query(criteria: list[SpecificAssetId]) -> list[str]:
    """The criteria as the ``assetIds`` query values ``GET /lookup/shells`` expects.

    Each criterion travels as its own base64url-encoded JSON object — that is
    the AAS v3 encoding, not a testlab convention — and it is the same encoding
    whichever registry is being searched, so both sides read it from here.
    """
    return [
        encode_as_base64_url_safe(json.dumps(entry.model_dump(exclude_none=True)))
        for entry in criteria
    ]


class ShellLookupOutput(StepPayload):
    """Shells a registry read returned.

    The one output shape of every step that answers with a collection of shells,
    so a script reads ``shell_ids`` and ``shell_descriptors`` the same way
    whether the shells were searched for or listed, and whether the registry
    searched was the run's own or a counterparty's.
    """

    shell_ids: list[str] = Field(
        default_factory=list, description="Identifiers of the shells that matched."
    )
    shell_descriptors: list[dict] = Field(
        default_factory=list,
        description="The descriptor document of each matching shell.",
    )


# ---------------------------------------------------------------------------
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

    def transport(self, context: StepContext) -> tuple[str, dict[str, str], float]:
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

    limit: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Maximum number of entries the registry may return in one page; "
            "its own default applies when omitted."
        ),
    )
    cursor: str | None = Field(
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


class ShellLookupParams(DataplaneParams):
    """Input contract of ``digital-twin-registry/consumer/dataplane/lookup_shell``."""

    specific_asset_ids: list[SpecificAssetId] = Field(
        min_length=1,
        description="Criteria the shell must match; all of them have to.",
    )

    def asset_id_query(self) -> list[str]:
        """The criteria as the ``assetIds`` query values the AAS API expects."""
        return _asset_ids_query(self.specific_asset_ids)


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
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[ShellLookupOutput]:
        base, headers, timeout = params.transport(context)

        url = f"{base}/lookup/shells"
        query = {"assetIds": params.asset_id_query()}
        response = await http_client.request(
            "GET", url, params=query, headers=headers, timeout=timeout
        )

        shell_ids = _shell_ids(response)
        descriptors = [
            document
            for shell_id in shell_ids
            if (document := await _shell_descriptor(base, shell_id, headers, timeout)) is not None
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

    cursor: str | None = Field(
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
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[ShellLookupPageOutput]:
        base, headers, timeout = params.transport(context)

        url = f"{base}/lookup/shellsByAssetLink"
        body = params.asset_link_body()
        query = params.page_query()
        response = await http_client.request(
            "POST",
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
            if (document := await _shell_descriptor(base, shell_id, headers, timeout)) is not None
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
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[ShellLookupPageOutput]:
        base, headers, timeout = params.transport(context)

        url = f"{base}/shell-descriptors"
        response = await http_client.request(
            "GET",
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
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        base, headers, timeout = params.transport(context)
        url, response = await _get_shell_descriptor(
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

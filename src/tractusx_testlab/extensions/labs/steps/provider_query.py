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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Listing what a provider connector holds — assets, policies, contract definitions. **Experimental.**

The delete steps take one id a test already knows. These find the ids a test
does not know — a connector-generated UUID, an offer an earlier run left
behind — so that ``labs/flow/for_each`` can hand them to those deletes one by one.
Each lists every page of the management API's ``/request`` query and keeps
the ids that start with ``id_prefix``; an empty prefix keeps all of them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field
from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

#: Entries asked for per page of a management-API query.
_PAGE_SIZE = 100
#: Pages read at most — a connector that ignores ``offset`` answers the same
#: page forever, and 10 000 entries is far past anything a lab connector holds.
_MAX_PAGES = 100
#: The EDC vocabulary a compacted management-API answer may or may not prefix.
_EDC_NS = "https://w3id.org/edc/v0.0.1/ns/"
#: The two policies a contract definition binds.
_POLICY_KEYS = ("accessPolicyId", "contractPolicyId")
#: Selector operands that name an asset by its own id.
_ASSET_ID_OPERANDS = frozenset({f"{_EDC_NS}id", "edc:id", "id", "@id"})


class QueryParams(StepParams):
    """Input contract shared by the three provider query steps."""

    id_prefix: str = Field(
        default="",
        description="Keep only the ids that start with this; empty keeps every one.",
    )


# ---------------------------------------------------------------------------
# labs/connector/provider/query_assets
# ---------------------------------------------------------------------------


class QueryAssetsOutput(StepPayload):
    """Output contract of ``labs/connector/provider/query_assets``."""

    asset_ids: list[str] = Field(description="Ids of the matching assets, in the order listed.")


@step("labs/connector/provider/query_assets")
class QueryAssetsStep(BaseStep[QueryParams, QueryAssetsOutput]):
    """List the ids of the assets the provider connector holds."""

    params_model = QueryParams
    output_model = QueryAssetsOutput

    async def execute(
        self, params: QueryParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[QueryAssetsOutput]:
        entries, request = _query_all(context, "assets")
        ids = _matching_ids(entries, params.id_prefix)
        return _output(QueryAssetsOutput(asset_ids=ids), request, len(ids))


# ---------------------------------------------------------------------------
# labs/connector/provider/query_policies
# ---------------------------------------------------------------------------


class QueryPoliciesOutput(StepPayload):
    """Output contract of ``labs/connector/provider/query_policies``."""

    policy_ids: list[str] = Field(
        description="Ids of the matching policy definitions, in the order listed."
    )


@step("labs/connector/provider/query_policies")
class QueryPoliciesStep(BaseStep[QueryParams, QueryPoliciesOutput]):
    """List the ids of the policy definitions the provider connector holds."""

    params_model = QueryParams
    output_model = QueryPoliciesOutput

    async def execute(
        self, params: QueryParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[QueryPoliciesOutput]:
        entries, request = _query_all(context, "policies")
        ids = _matching_ids(entries, params.id_prefix)
        return _output(QueryPoliciesOutput(policy_ids=ids), request, len(ids))


# ---------------------------------------------------------------------------
# labs/connector/provider/query_contract_definitions
# ---------------------------------------------------------------------------


class QueryContractDefinitionsParams(QueryParams):
    """Input contract of ``labs/connector/provider/query_contract_definitions``."""

    asset_id_prefix: str = Field(
        default="",
        description=(
            "Also keep a definition whose asset selector names an asset id that "
            "starts with this — the way to find an offer whose own id the "
            "connector generated."
        ),
    )


class QueryContractDefinitionsOutput(StepPayload):
    """Output contract of ``labs/connector/provider/query_contract_definitions``."""

    contract_definition_ids: list[str] = Field(
        description="Ids of the matching contract definitions, in the order listed."
    )
    policy_ids: list[str] = Field(
        description="Access and contract policies the matching definitions bind, once each."
    )
    asset_ids: list[str] = Field(
        description="Asset ids the matching definitions' selectors name, once each."
    )


@step("labs/connector/provider/query_contract_definitions")
class QueryContractDefinitionsStep(
    BaseStep[QueryContractDefinitionsParams, QueryContractDefinitionsOutput]
):
    """List the contract definitions the provider connector holds.

    A definition is kept when its id starts with ``id_prefix`` or its selector
    names an asset starting with ``asset_id_prefix``; with neither given, every
    definition is. Besides their ids it publishes the policies and assets the
    kept definitions bind, so a test can withdraw a whole offer — definition
    first, then its policies, then its assets — without knowing any of them.
    """

    params_model = QueryContractDefinitionsParams
    output_model = QueryContractDefinitionsOutput

    async def execute(
        self,
        params: QueryContractDefinitionsParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[QueryContractDefinitionsOutput]:
        entries, request = _query_all(context, "contract_definitions")
        kept = [entry for entry in entries if _is_kept(entry, params)]
        output = QueryContractDefinitionsOutput(
            contract_definition_ids=_matching_ids(kept, ""),
            policy_ids=_unique(
                str(policy_id)
                for entry in kept
                for policy_id in (_field(entry, key) for key in _POLICY_KEYS)
                if policy_id
            ),
            asset_ids=_unique(asset_id for entry in kept for asset_id in _selected_assets(entry)),
        )
        return _output(output, request, len(kept))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _query_all(context: StepContext, controller: str) -> tuple[list[dict], HttpRequest]:
    """Every entry of one management-API collection, read page by page."""
    provider = context.dataspace.provider()
    endpoint = getattr(provider, controller)
    url = context.dataspace.provider_endpoint_url(controller, "request")
    entries: list[dict] = []
    for page_number in range(_MAX_PAGES):
        spec = ModelFactory.get_queryspec_model(
            dataspace_version=provider.dataspace_version,
            offset=page_number * _PAGE_SIZE,
            limit=_PAGE_SIZE,
            filter_expression=[],
        )
        response = endpoint.query(spec)
        page = _page_of(response, url)
        entries.extend(page)
        if len(page) < _PAGE_SIZE:
            break
    return entries, HttpRequest(method="POST", url=url)


def _page_of(response: Any, url: str) -> list[dict]:
    """The entries of one query answer, or a failure that names what came back."""
    status = getattr(response, "status_code", None)
    if status != 200:
        raise ValueError(f"Query {url} answered {status}, expected 200 with a JSON array.")
    body = response.json()
    if not isinstance(body, list):
        raise ValueError(f"Query {url} answered {type(body).__name__}, expected a JSON array.")
    return [entry for entry in body if isinstance(entry, dict)]


def _matching_ids(entries: list[dict], prefix: str) -> list[str]:
    return _unique(
        str(entry["@id"])
        for entry in entries
        if entry.get("@id") and str(entry["@id"]).startswith(prefix)
    )


def _is_kept(entry: dict, params: QueryContractDefinitionsParams) -> bool:
    if not params.id_prefix and not params.asset_id_prefix:
        return True
    if params.id_prefix and str(entry.get("@id", "")).startswith(params.id_prefix):
        return True
    return bool(params.asset_id_prefix) and any(
        asset_id.startswith(params.asset_id_prefix) for asset_id in _selected_assets(entry)
    )


def _selected_assets(entry: dict) -> list[str]:
    """The asset ids a contract definition's selector names; one criterion or a list."""
    selector = _field(entry, "assetsSelector") or []
    criteria = selector if isinstance(selector, list) else [selector]
    ids: list[str] = []
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        if _field(criterion, "operandLeft") not in _ASSET_ID_OPERANDS:
            continue
        right = _field(criterion, "operandRight")
        ids.extend(str(value) for value in (right if isinstance(right, list) else [right]) if value)
    return ids


def _field(entry: dict, name: str) -> Any:
    """Read *name* however the answer was compacted: bare, ``edc:``-prefixed or full IRI."""
    for key in (name, f"edc:{name}", f"{_EDC_NS}{name}"):
        if key in entry:
            return entry[key]
    return None


def _unique(values: Any) -> list[str]:
    """*values* in order, each once."""
    return list(dict.fromkeys(values))


def _output(value: StepPayload, request: HttpRequest, count: int) -> StepOutput[Any]:
    return StepOutput(
        value=value,
        request=request,
        response=HttpResponse(status_code=200, body={"count": count}),
    )

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Catalog query steps — DSP and SDK-based provider catalog lookups."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field
from tractusx_sdk.dataspace.tools import DspTools

from tractusx_testlab.models import (
    HttpRequest,
    HttpResponse,
    StepDefinition,
    StepExecutionError,
)
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.counter_party import CounterPartyParams
from tractusx_testlab.steps.dsp_protocol import DspProtocolParams
from tractusx_testlab.steps.shared_models import (
    CatalogOutput,
    CatalogPayload,
    FilterExpression,
    StepParams,
    as_dataset_list,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

__all__ = [
    "CatalogOfferOutput",
    "CatalogOutput",
    "CatalogPayload",
    "CounterPartyParams",
    "FilterExpression",
    "QueryCatalogByAssetIdParams",
    "QueryCatalogByAssetIdStep",
    "QueryCatalogByBpnlParams",
    "QueryCatalogByBpnlStep",
    "QueryCatalogParams",
    "QueryCatalogStep",
]


# ---------------------------------------------------------------------------
# connector/consumer/query_catalog
# ---------------------------------------------------------------------------


class QueryCatalogParams(CounterPartyParams, DspProtocolParams):
    """Input contract of ``connector/consumer/query_catalog``."""

    filters: list[FilterExpression] = Field(
        default_factory=list,
        description="Filter criteria applied to the catalog request.",
    )


@step("connector/consumer/query_catalog")
class QueryCatalogStep(BaseStep[QueryCatalogParams, CatalogOutput]):
    """Query a provider's catalog via the SDK connector consumer service.

    Returns the catalog document and its offers side by side, so a ``returns:``
    block reads ``datasets`` rather than the JSON-LD key the provider's DSP
    generation happens to spell them with, and downstream steps read the same
    offers.
    """

    params_model = QueryCatalogParams
    output_model = CatalogOutput

    async def execute(
        self,
        params: QueryCatalogParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[CatalogOutput]:
        consumer = context.dataspace.consumer()
        party = params.counter_party(context)
        catalog = await sdk_call.run(
            consumer.get_catalog_with_filter,
            counter_party_id=party.identity,
            counter_party_address=party.address,
            filter_expression=[entry.to_sdk() for entry in params.filters],
            **params.sdk_protocol(),
        )

        url = context.dataspace.consumer_endpoint_url("catalogs", "request")
        request = HttpRequest(method="POST", url=url, body=params.model_dump(mode="json"))
        if not catalog:
            raise StepExecutionError(
                self.step_type,
                f"the provider returned no catalog from {url}. The step declares a "
                f"catalog and its offers, and has neither.",
            )

        datasets = as_dataset_list(catalog)
        return StepOutput(
            value=CatalogOutput(catalog=catalog, datasets=datasets),
            request=request,
            response=HttpResponse(status_code=200, body=catalog),
        )


# ---------------------------------------------------------------------------
# connector/consumer/query_catalog_by_asset_id
# ---------------------------------------------------------------------------


class QueryCatalogByAssetIdParams(CounterPartyParams, DspProtocolParams):
    """Input contract of ``connector/consumer/query_catalog_by_asset_id``.

    The asset ID is the whole filter.  Narrowing the result further by policy is
    what ``pull_data_filtered_by_policy`` and ``do_dsp`` are for; a catalog query
    that also picked its offer by policy was two steps wearing one name, and the
    policy half of it silently selected nothing whenever a script left it out.
    """

    asset_id: str = Field(description="Asset ID the catalog is filtered by.")


class CatalogOfferOutput(CatalogOutput):
    """Output contract of ``connector/consumer/query_catalog_by_asset_id``.

    Extends the catalog document with the first offer it carries, which is what
    ``negotiate`` reads back when a script does not name an offer itself.  Both
    fields stay unset when the catalog carries no offer at all — selection is
    best-effort here and ``negotiate`` is what reports the failure.
    """

    catalog_asset_id: Any | None = Field(
        default=None,
        description="Asset ID of the first offer in the catalog.",
    )
    catalog_policy: Any | None = Field(
        default=None,
        description="The ODRL policy that offer is made under.",
    )


@step("connector/consumer/query_catalog_by_asset_id")
class QueryCatalogByAssetIdStep(BaseStep[QueryCatalogByAssetIdParams, CatalogOfferOutput]):
    """Query the catalog filtered by a specific asset ID.

    Returns the catalog's first offer as ``catalog_asset_id`` / ``catalog_policy``
    for the negotiation step that follows.  Which policy that offer carries is
    reported, not judged: a step that asserts on the policy reads it from the
    output, and a step that must *only* accept certain policies is
    ``pull_data_filtered_by_policy``.
    """

    params_model = QueryCatalogByAssetIdParams
    output_model = CatalogOfferOutput

    async def execute(
        self,
        params: QueryCatalogByAssetIdParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[CatalogOfferOutput]:
        consumer = context.dataspace.consumer()
        party = params.counter_party(context)
        result = await sdk_call.run(
            consumer.get_catalog_by_asset_id,
            counter_party_id=party.identity,
            counter_party_address=party.address,
            asset_id=params.asset_id,
            **params.sdk_protocol(),
        )
        url = context.dataspace.consumer_endpoint_url("catalogs", "request")

        value = CatalogOfferOutput(catalog=result, datasets=as_dataset_list(result))
        offer = _first_offer(result)
        if offer is not None:
            value.catalog_asset_id, value.catalog_policy = offer

        return StepOutput(
            value=value,
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(status_code=200, body=result),
        )


def _first_offer(catalog: Any) -> tuple[Any, Any] | None:
    """Pick the catalog's first offer and the policy it is made under, or nothing.

    ``allowed_policies=None`` is the SDK's "accept any policy"; ``[]`` is its
    "accept none", and passing the latter is how this step used to select
    nothing at all whenever a script named no policies — the empty default of a
    filter that has now been removed.
    """
    if not catalog:
        return None
    try:
        matches = DspTools.filter_assets_and_policies(catalog=catalog, allowed_policies=None)
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    if not matches:
        return None
    asset_id, policy = matches[0]
    return asset_id, policy


# ---------------------------------------------------------------------------
# connector/consumer/query_catalog_by_bpnl
# ---------------------------------------------------------------------------


class QueryCatalogByBpnlParams(StepParams):
    """Input contract of ``connector/consumer/query_catalog_by_bpnl``."""

    bpnl: str = Field(description="BPN used to discover the counter-party's connector.")
    counter_party_address: str | None = Field(
        default=None,
        description="DSP endpoint; when omitted it is resolved from the BPN by discovery.",
    )
    filters: list[FilterExpression] = Field(
        default_factory=list,
        description="Filter criteria applied to the catalog request.",
    )


@step("connector/consumer/query_catalog_by_bpnl")
class QueryCatalogByBpnlStep(BaseStep[QueryCatalogByBpnlParams, CatalogOutput]):
    """Query the catalog using BPNL-based connector discovery.

    Alone among the catalog steps this takes no ``protocol``: discovery is what
    answers with one, so a protocol given here would be an assumption competing
    with the connector's own answer.  Pin it by discovering explicitly with
    ``connector/consumer/discover_connector`` and passing the endpoint it
    resolves to ``query_catalog``.
    """

    params_model = QueryCatalogByBpnlParams
    output_model = CatalogOutput

    async def execute(
        self,
        params: QueryCatalogByBpnlParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[CatalogOutput]:
        consumer = context.dataspace.consumer()
        result = await sdk_call.run(
            consumer.get_catalog_with_bpnl,
            bpnl=params.bpnl,
            counter_party_address=params.counter_party_address,
            filter_expression=[entry.to_sdk() for entry in params.filters] or None,
        )
        url = context.dataspace.consumer_endpoint_url("catalogs", "request")
        return StepOutput(
            value=CatalogOutput(catalog=result, datasets=as_dataset_list(result)),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(status_code=200, body=result),
        )

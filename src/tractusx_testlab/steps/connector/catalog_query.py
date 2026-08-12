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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Catalog query steps — DSP and SDK-based provider catalog lookups."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

from tractusx_sdk.dataspace.tools import DspTools
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import (
    DATASET_KEY,
    CatalogDatasetsExports,
    CatalogOutput,
    CatalogPayload,
    CounterPartyParams,
    FilterExpression,
    StepParams,
    as_dataset_list,
)
from tractusx_testlab.steps.base import BaseStep, StepExports, StepOutput
from tractusx_testlab.syntax.context_vars import CATALOG_ASSET_ID, CATALOG_POLICY

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

__all__ = [
    "DATASET_KEY",
    "CatalogOutput",
    "CatalogPayload",
    "CounterPartyParams",
    "FilterExpression",
    "QueryCatalogByAssetIdExports",
    "QueryCatalogByAssetIdParams",
    "QueryCatalogByAssetIdStep",
    "QueryCatalogByBpnlParams",
    "QueryCatalogByBpnlStep",
    "QueryCatalogExports",
    "QueryCatalogParams",
    "QueryCatalogStep",
]


# ---------------------------------------------------------------------------
# connector/consumer/query_catalog
# ---------------------------------------------------------------------------


class QueryCatalogParams(CounterPartyParams):
    """Input contract of ``connector/consumer/query_catalog``."""

    filters: list[FilterExpression] = Field(
        default_factory=list,
        description="Filter criteria applied to the catalog request.",
    )


#: ``query_catalog`` publishes exactly the offers every catalog step publishes.
QueryCatalogExports = CatalogDatasetsExports


@step("connector/consumer/query_catalog")
class QueryCatalogStep(BaseStep[QueryCatalogParams, CatalogOutput]):
    """Query a provider's catalog via the SDK connector consumer service.

    Returns the catalog document and its offers side by side, so a ``returns:``
    block reads ``datasets`` rather than the JSON-LD ``dcat:dataset`` key, and
    publishes the same offers for downstream steps.
    """

    params_model = QueryCatalogParams
    output_model = CatalogOutput
    exports_model = QueryCatalogExports

    async def execute(
        self,
        params: QueryCatalogParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[CatalogOutput]:
        consumer = context.get_consumer_service()
        catalog = consumer.get_catalog_with_filter(
            counter_party_id=params.counter_party_id,
            counter_party_address=params.counter_party_address,
            filter_expression=[entry.to_sdk() for entry in params.filters],
        )

        url = context.get_consumer_endpoint_url("catalogs", "request")
        request = HttpRequest(method="POST", url=url, body=params.model_dump(mode="json"))
        if not catalog:
            logger.error("Catalog request returned no result: url=%s", url)
            return StepOutput(
                value=None,
                request=request,
                response=HttpResponse(status_code=500, body=None),
            )

        datasets = as_dataset_list(catalog)
        return StepOutput(
            value=CatalogOutput(catalog=catalog, datasets=datasets),
            request=request,
            response=HttpResponse(status_code=200, body=catalog),
            exports=QueryCatalogExports(datasets=datasets),
        )


# ---------------------------------------------------------------------------
# connector/consumer/query_catalog_by_asset_id
# ---------------------------------------------------------------------------


class QueryCatalogByAssetIdParams(StepParams):
    """Input contract of ``connector/consumer/query_catalog_by_asset_id``."""

    counter_party_id: str = Field(description="BPN of the counter-party.")
    counter_party_address: str = Field(
        description="DSP endpoint of the counter-party connector."
    )
    asset_id: str = Field(description="Asset ID the catalog is filtered by.")
    expected_policies: list[dict] = Field(
        default_factory=list,
        description="Policies accepted for the returned offer; the first match is exported.",
    )


class QueryCatalogByAssetIdExports(StepExports):
    """Context variables published by ``connector/consumer/query_catalog_by_asset_id``.

    Both stay unset when no offer matches ``expected_policies`` — selection is
    best-effort here and ``negotiate`` is what reports the failure.
    """

    catalog_asset_id: Optional[Any] = Field(
        default=None,
        alias=CATALOG_ASSET_ID,
        description="Asset ID of the first offer whose policy is expected.",
    )
    catalog_policy: Optional[Any] = Field(
        default=None,
        alias=CATALOG_POLICY,
        description="The accepted ODRL policy of that offer.",
    )


@step("connector/consumer/query_catalog_by_asset_id")
class QueryCatalogByAssetIdStep(BaseStep[QueryCatalogByAssetIdParams, CatalogOutput]):
    """Query the catalog filtered by a specific asset ID.

    Publishes the first offer matching ``expected_policies`` as ``catalog_asset_id`` /
    ``catalog_policy`` for the negotiation step that follows.
    """

    params_model = QueryCatalogByAssetIdParams
    output_model = CatalogOutput
    exports_model = QueryCatalogByAssetIdExports

    async def execute(
        self,
        params: QueryCatalogByAssetIdParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[CatalogOutput]:
        consumer = context.get_consumer_service()
        result = consumer.get_catalog_by_asset_id(
            counter_party_id=params.counter_party_id,
            counter_party_address=params.counter_party_address,
            asset_id=params.asset_id,
        )
        url = context.get_consumer_endpoint_url("catalogs", "request")

        return StepOutput(
            value=CatalogOutput(catalog=result, datasets=as_dataset_list(result)),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(status_code=200 if result else 500, body=result),
            exports=_select_offer(result, params.expected_policies),
        )


def _select_offer(catalog: Any, expected_policies: list[dict]) -> QueryCatalogByAssetIdExports:
    """Pick the first offer matching ``expected_policies``, or export nothing."""
    if not catalog:
        return QueryCatalogByAssetIdExports()
    try:
        matches = DspTools.filter_assets_and_policies(catalog=catalog, allowed_policies=expected_policies)
    except (KeyError, TypeError, ValueError, IndexError):
        return QueryCatalogByAssetIdExports()
    if not matches:
        return QueryCatalogByAssetIdExports()
    asset_id, policy = matches[0]
    return QueryCatalogByAssetIdExports(catalog_asset_id=asset_id, catalog_policy=policy)


# ---------------------------------------------------------------------------
# connector/consumer/query_catalog_by_bpnl
# ---------------------------------------------------------------------------


class QueryCatalogByBpnlParams(StepParams):
    """Input contract of ``connector/consumer/query_catalog_by_bpnl``."""

    bpnl: str = Field(description="BPN used to discover the counter-party's connector.")
    counter_party_address: Optional[str] = Field(
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

    Publishes no context variables.
    """

    params_model = QueryCatalogByBpnlParams
    output_model = CatalogOutput

    async def execute(
        self,
        params: QueryCatalogByBpnlParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[CatalogOutput]:
        consumer = context.get_consumer_service()
        result = consumer.get_catalog_with_bpnl(
            bpnl=params.bpnl,
            counter_party_address=params.counter_party_address,
            filter_expression=[entry.to_sdk() for entry in params.filters] or None,
        )
        url = context.get_consumer_endpoint_url("catalogs", "request")
        return StepOutput(
            value=CatalogOutput(catalog=result, datasets=as_dataset_list(result)),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(status_code=200 if result else 500, body=result),
        )

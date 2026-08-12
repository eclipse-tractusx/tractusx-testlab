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

"""Catalog query step with multiple filter expressions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import (
    CatalogDatasetsExports,
    CatalogOutput,
    CounterPartyParams,
    FilterExpressionParams,
    as_dataset_list,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# connector/consumer/query_catalog_with_filters
# ---------------------------------------------------------------------------


class QueryCatalogWithFiltersParams(CounterPartyParams, FilterExpressionParams):
    """Input contract of ``connector/consumer/query_catalog_with_filters``."""


@step("connector/consumer/query_catalog_with_filters")
class QueryCatalogWithFiltersStep(BaseStep[QueryCatalogWithFiltersParams, CatalogOutput]):
    """Query a provider's catalog with multiple filter expressions via the SDK.

    Filter criteria are translated by the SDK's own ``get_filter_expression``,
    so they carry whatever JSON-LD context the negotiated dataspace version
    expects.
    """

    params_model = QueryCatalogWithFiltersParams
    output_model = CatalogOutput
    exports_model = CatalogDatasetsExports

    async def execute(
        self,
        params: QueryCatalogWithFiltersParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[CatalogOutput]:
        consumer = context.get_consumer_service()
        filter_expression = [
            consumer.get_filter_expression(
                key=entry.operand_left, value=entry.operand_right, operator=entry.operator
            )
            for entry in params.filters
        ]

        catalog = consumer.get_catalog_with_filter(
            counter_party_id=params.counter_party_id,
            counter_party_address=params.counter_party_address,
            filter_expression=filter_expression,
        )

        url = f"{params.counter_party_address}/catalog/request"
        request = HttpRequest(method="POST", url=url, body=params.model_dump(mode="json"))
        if not catalog:
            logger.error("Filtered catalog request returned no result: url=%s", url)
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
            exports=CatalogDatasetsExports(datasets=datasets),
        )

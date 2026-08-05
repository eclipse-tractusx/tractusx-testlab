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

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


@step("connector/consumer/query_catalog_with_filters")
class QueryCatalogWithFiltersStep(BaseStep):
    """Query a provider's catalog with multiple filter expressions via the SDK."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        consumer = context.get_consumer_service()
        counter_party_address = params.get("counter_party_address") or params.get("provider_url", "")
        counter_party_id = params.get("counter_party_id") or params.get("bpnl", "")
        filter_expression = self._build_filter_expression(consumer, params.get("filters", []))

        catalog = consumer.get_catalog_with_filter(
            counter_party_id=counter_party_id,
            counter_party_address=counter_party_address,
            filter_expression=filter_expression,
        )

        url = f"{counter_party_address}/catalog/request"
        if not catalog:
            logger.error("Filtered catalog request returned no result: url=%s", url)
            return StepOutput(
                value=None,
                request=HttpRequest(method="POST", url=url, body=params),
                response=HttpResponse(status_code=500, body=None),
            )

        datasets = catalog.get("dcat:dataset", [])
        if isinstance(datasets, dict):
            datasets = [datasets]
        context.set_variable("datasets", datasets)

        return StepOutput(
            value={"catalog": catalog, "datasets": datasets},
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(status_code=200, body=catalog),
        )

    @staticmethod
    def _build_filter_expression(consumer: object, filters: list) -> list[dict]:
        """Convert block-style filters to SDK filter dicts via ``get_filter_expression``."""
        expressions: list[dict] = []
        for entry in filters:
            if not isinstance(entry, dict):
                continue
            key = entry.get("operand_left", entry.get("operandLeft", ""))
            value = entry.get("operand_right", entry.get("operandRight", ""))
            operator = entry.get("operator", "=")
            expressions.append(consumer.get_filter_expression(key=key, value=value, operator=operator))
        return expressions

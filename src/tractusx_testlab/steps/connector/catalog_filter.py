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
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.steps.connector.consume import _create_dsp_consumer

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


@step("connector/consumer/query_catalog_with_filters")
class QueryCatalogWithFiltersStep(BaseStep):
    """Query a provider's catalog with multiple filter expressions."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        counter_party_address = params.get("counter_party_address") or params.get("provider_url", "")
        filters = params.get("filters", [])

        # Build composite filter expression from filter list
        filter_expression = self._build_filter_expression(filters)

        dsp_consumer = _create_dsp_consumer(counter_party_address)
        response = dsp_consumer.request_catalog(filter_expression=filter_expression)

        url = f"{counter_party_address}/catalog/request"
        if response.status_code != 200:
            logger.error(
                "Filtered catalog request failed: status=%d, url=%s",
                response.status_code, url,
            )
            return StepOutput(
                value=None,
                request=HttpRequest(method="POST", url=url, body=params),
                response=HttpResponse(status_code=response.status_code, body=None),
            )

        result = response.json()

        datasets = result.get("dcat:dataset", [])
        if isinstance(datasets, dict):
            datasets = [datasets]
        context.set_variable("datasets", datasets)

        return StepOutput(
            value={"catalog": result, "datasets": datasets},
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(status_code=200, body=result),
        )

    @staticmethod
    def _build_filter_expression(filters: list) -> list | None:
        """Convert block-style filter list to SDK filter expression format."""
        if not filters:
            return None

        expressions = []
        for f in filters:
            if isinstance(f, dict):
                expressions.append({
                    "operandLeft": f.get("operand_left", f.get("operandLeft", "")),
                    "operator": f.get("operator", "="),
                    "operandRight": f.get("operand_right", f.get("operandRight", "")),
                })
        return expressions if expressions else None

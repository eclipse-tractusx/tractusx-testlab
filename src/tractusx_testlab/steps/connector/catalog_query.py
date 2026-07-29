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
from typing import TYPE_CHECKING

from tractusx_sdk.dataspace.tools.dsp_tools import DspTools
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import CATALOG_POLICY, CATALOG_TARGET

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


def _resolve_filter_expression(params: dict) -> list[dict]:
    """Return the SDK filter expression from explicit or nested ``filter`` params."""
    filter_expression = params.get("filter_expression")
    if not filter_expression:
        filter_dict = params.get("filter", {})
        if isinstance(filter_dict, dict):
            filter_expression = filter_dict.get("filter_expression")
    return filter_expression or []


@step("connector/consumer/query_catalog", aliases=["query_catalog"])
class QueryCatalogStep(BaseStep):
    """Query a provider's catalog via the SDK connector consumer service."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        consumer = context.get_consumer_service()
        counter_party_address = params.get("counter_party_address") or params.get("provider_url", "")
        counter_party_id = params.get("counter_party_id") or params.get("bpnl", "")
        filter_expression = _resolve_filter_expression(params)

        catalog = consumer.get_catalog_with_filter(
            counter_party_id=counter_party_id,
            counter_party_address=counter_party_address,
            filter_expression=filter_expression,
        )

        url = f"{counter_party_address}/catalog/request"
        if not catalog:
            logger.error("Catalog request returned no result: url=%s", url)
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
            value=catalog,
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(status_code=200, body=catalog),
        )


@step("connector/consumer/query_catalog_by_asset_id", aliases=["query_catalog_by_asset_id"])
class QueryCatalogByAssetIdStep(BaseStep):
    """Query the catalog filtered by a specific asset ID."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        consumer = context.get_consumer_service()
        result = consumer.get_catalog_by_asset_id(
            counter_party_id=params["counter_party_id"],
            counter_party_address=params["counter_party_address"],
            asset_id=params["asset_id"],
        )
        url = f"{context.get_consumer_base_url()}/v3/catalog/request"

        if result:
            try:
                valid_assets_policies = DspTools.filter_assets_and_policies(
                    catalog=result,
                    allowed_policies=params.get("policies", []),
                )
                if valid_assets_policies:
                    target, policy = valid_assets_policies[0]
                    context.set_variable(CATALOG_TARGET, target)
                    context.set_variable(CATALOG_POLICY, policy)
            except (KeyError, TypeError, ValueError, IndexError):
                pass  # Catalog extraction is best-effort; negotiate_contract will fail explicitly

        return StepOutput(
            value=result,
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(status_code=200 if result else 500, body=result),
        )


@step("connector/consumer/query_catalog_by_bpnl", aliases=["query_catalog_by_bpnl"])
class QueryCatalogByBpnlStep(BaseStep):
    """Query the catalog using BPNL-based connector discovery."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        consumer = context.get_consumer_service()
        result = consumer.get_catalog_with_bpnl(
            bpnl=params["bpnl"],
            counter_party_address=params.get("counter_party_address"),
            filter_expression=params.get("filter_expression"),
        )
        url = f"{context.get_consumer_base_url()}/v3/catalog/request"
        return StepOutput(
            value=result,
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(status_code=200 if result else 500, body=result),
        )

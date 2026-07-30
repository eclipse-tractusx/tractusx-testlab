#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""DSP catalog request step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import (
    DSP_CATALOG,
    DSP_OFFER,
    DSP_OFFER_ID,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/dsp/catalog_request")
class DspCatalogRequestStep(BaseStep):
    """Send a DSP CatalogRequestMessage directly to the provider.

    Constructs a proper ``dspace:CatalogRequestMessage`` in JSON-LD
    and sends it to the provider's ``catalog/request`` endpoint.
    This tests the actual DSP protocol wire format, not the Management API.

    Params:
        service (str, optional): Named DSP_CONSUMER service to use.
        filter_expression (list[dict], optional): DCAT filter criteria.

    Stores in context:
        dsp_catalog: The full catalog response.
        dsp_offer: The first offer found (if any).
        dsp_offer_id: The first offer ID found (if any).
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition,
    ) -> StepOutput:
        dsp = context.get_dsp_consumer_service(params.get("service"))
        filter_expression = params.get("filter_expression")

        resp = dsp.request_catalog(filter_expression=filter_expression)

        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        # Auto-extract first offer for downstream steps
        if isinstance(body, dict):
            context.set_variable(DSP_CATALOG, body)
            datasets = body.get("dcat:dataset") or body.get("dspace:dataset") or []
            if isinstance(datasets, dict):
                datasets = [datasets]
            if datasets:
                first = datasets[0]
                offer = first.get("odrl:hasPolicy") or first.get("dspace:hasPolicy")
                if isinstance(offer, list) and offer:
                    offer = offer[0]
                if offer:
                    context.set_variable(DSP_OFFER, offer)
                    context.set_variable(DSP_OFFER_ID, offer.get("@id"))

        return StepOutput(
            value=body,
            request=HttpRequest(
                method="POST",
                url=f"{dsp.base_url}/catalog/request",
                body={"filter_expression": filter_expression},
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
            ),
        )

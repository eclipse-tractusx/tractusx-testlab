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

"""Data-plane interaction steps — fetch data through EDR endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import (
    DATAPLANE_ENDPOINT,
    EDR_TOKEN,
    TRANSFER_ID,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/dataplane/http_request")
class DataplaneCallStep(BaseStep):
    """Fetch data from a data-plane endpoint using an EDR token."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        endpoint = params.get("dataplane_url") or params.get("url") or params.get("endpoint") or context.get_variable(DATAPLANE_ENDPOINT)
        if isinstance(endpoint, dict):
            endpoint = endpoint.get("endpoint") or endpoint.get("baseUrl")
        path = params.get("path", "")
        if path:
            endpoint = endpoint.rstrip("/") + "/" + path.lstrip("/")
        token = params.get("edr_token") or params.get("token") or context.get_variable(EDR_TOKEN)
        method = params.get("method", "GET").upper()
        body = params.get("body")
        headers = {"Authorization": token, **(params.get("headers") or {})}
        timeout = params.get("timeout", context.config.default_timeout_s)

        req = HttpRequest(method=method, url=endpoint, headers=headers, body=body)
        resp = requests.request(method, endpoint, headers=headers, json=body, timeout=timeout)

        return StepOutput(
            value=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
            request=req,
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.text,
            ),
        )


@step("connector/consumer/get_edr")
class GetEdrStep(BaseStep):
    """Retrieve the EDR entry for a completed transfer."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        consumer = context.get_consumer_service()
        transfer_id = params.get("transfer_id") or context.get_variable(TRANSFER_ID)
        url = f"{context.get_consumer_base_url()}/v3/edrs/{transfer_id}/dataaddress"

        edr = consumer.get_edr(transfer_id=transfer_id)

        if edr:
            context.set_variable(DATAPLANE_ENDPOINT, edr.get("endpoint"))
            context.set_variable(EDR_TOKEN, edr.get("authorization"))

        return StepOutput(
            value=edr,
            request=HttpRequest(method="GET", url=url),
            response=HttpResponse(status_code=200 if edr else 404, body=edr),
        )

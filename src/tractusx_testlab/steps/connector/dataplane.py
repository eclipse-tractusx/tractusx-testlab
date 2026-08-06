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

from typing import TYPE_CHECKING, Any, Optional

import requests
from pydantic import AliasChoices, Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import (
    DataAddressPayload,
    DataplaneExports,
    HttpBodyOutput,
    HttpCallParams,
    StepParams,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import (
    DATAPLANE_ENDPOINT,
    EDR_TOKEN,
    TRANSFER_ID,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# connector/dataplane/http_request
# ---------------------------------------------------------------------------


class DataplaneCallParams(HttpCallParams):
    """Input contract of ``connector/dataplane/http_request``.

    Left alone, both the endpoint and the token come from whichever step
    completed the transfer — that is the ``dataplane_endpoint``/``edr_token``
    pair declared by
    :class:`~tractusx_testlab.steps._contracts.DataplaneExports`.
    """

    endpoint: Any = Field(
        default=None,
        validation_alias=AliasChoices("dataplane_url", "url", "endpoint"),
        description=(
            "Data-plane URL, or a data address object to read it from; falls back "
            "to the 'dataplane_endpoint' context variable."
        ),
    )
    path: str = Field(default="", description="Path appended to the data-plane URL.")
    token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("edr_token", "token"),
        description="EDR authorization token; falls back to the 'edr_token' context variable.",
    )

    def endpoint_url(self, fallback: Any) -> str:
        """The URL to call, resolved from whichever form the endpoint arrived in."""
        endpoint = self.endpoint or fallback
        if isinstance(endpoint, dict):
            endpoint = endpoint.get("endpoint") or endpoint.get("baseUrl")
        if not self.path:
            return str(endpoint)
        return str(endpoint).rstrip("/") + "/" + self.path.lstrip("/")


@step("connector/dataplane/http_request")
class DataplaneCallStep(BaseStep[DataplaneCallParams, HttpBodyOutput]):
    """Fetch data from a data-plane endpoint using an EDR token.

    This is the far end of the DSP flow: ``do_dsp`` or ``transfer_data``
    publishes where the data is and how to authorize for it, and this step
    reads exactly those two variables.
    """

    params_model = DataplaneCallParams
    output_model = HttpBodyOutput

    async def execute(
        self, params: DataplaneCallParams, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput[HttpBodyOutput]:
        url = params.endpoint_url(context.get_variable(DATAPLANE_ENDPOINT))
        token = params.token or context.get_variable(EDR_TOKEN)
        headers = {"Authorization": token, **params.headers}
        timeout = params.timeout_or(context.config.default_timeout_s)

        resp = requests.request(
            params.method, url, headers=headers, json=params.body, timeout=timeout
        )
        is_json = resp.headers.get("content-type", "").startswith("application/json")

        return StepOutput(
            value=HttpBodyOutput(resp.json() if is_json else resp.text),
            request=HttpRequest(
                method=params.method, url=url, headers=headers, body=params.body
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.text,
            ),
        )


# ---------------------------------------------------------------------------
# connector/consumer/get_edr
# ---------------------------------------------------------------------------


class GetEdrParams(StepParams):
    """Input contract of ``connector/consumer/get_edr``."""

    transfer_id: Optional[str] = Field(
        default=None,
        description=(
            "Transfer process to read the EDR of; falls back to the "
            "'transfer_id' context variable."
        ),
    )


@step("connector/consumer/get_edr")
class GetEdrStep(BaseStep[GetEdrParams, DataAddressPayload]):
    """Retrieve the EDR data address for a completed transfer.

    Publishes the same data-plane pair as ``transfer_data``, so it can stand in
    for that step when the transfer was started elsewhere.
    """

    params_model = GetEdrParams
    output_model = DataAddressPayload
    exports_model = DataplaneExports

    async def execute(
        self, params: GetEdrParams, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput[DataAddressPayload]:
        consumer = context.get_consumer_service()
        transfer_id = params.transfer_id or context.get_variable(TRANSFER_ID)
        url = context.get_consumer_endpoint_url("edrs", transfer_id, "dataaddress")

        edr = consumer.get_edr(transfer_id=transfer_id)

        return StepOutput(
            value=DataAddressPayload.of(edr),
            request=HttpRequest(method="GET", url=url),
            response=HttpResponse(status_code=200 if edr else 404, body=edr),
            exports=DataplaneExports(
                dataplane_endpoint=(edr or {}).get("endpoint"),
                edr_token=(edr or {}).get("authorization"),
            ),
        )

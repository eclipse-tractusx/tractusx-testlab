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

import logging
from typing import TYPE_CHECKING, Any, Optional

import requests
from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import (
    DataAddressPayload,
    DataplaneExports,
    HttpBodyOutput,
    HttpCallParams,
    StepParams,
    data_address_token,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import (
    DATA_ADDRESS,
    EDR_TOKEN,
    TRANSFER_ID,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# connector/dataplane/http_request
# ---------------------------------------------------------------------------


class DataplaneCallParams(HttpCallParams):
    """Input contract of ``connector/dataplane/http_request``.

    Left alone, both the URL and the token come from whichever step completed
    the transfer — that is the ``data_address``/``edr_token`` pair declared by
    :class:`~tractusx_testlab.steps._contracts.DataplaneExports`.
    """

    dataplane_url: Any = Field(
        default=None,
        description=(
            "Data-plane URL, or a data address object to read it from; falls back "
            "to the 'data_address' context variable."
        ),
    )
    path: str = Field(default="", description="Path appended to the data-plane URL.")
    edr_token: Optional[str] = Field(
        default=None,
        description="EDR authorization token; falls back to the 'edr_token' context variable.",
    )

    def resolved_url(self, fallback: Any) -> str:
        """The URL to call, resolved from whichever form the data address arrived in."""
        endpoint = self.dataplane_url or fallback
        if isinstance(endpoint, dict):
            endpoint = endpoint.get("endpoint") or endpoint.get("baseUrl")
        if not self.path:
            return str(endpoint)
        return str(endpoint).rstrip("/") + "/" + self.path.lstrip("/")


@step("connector/dataplane/http_request")
class DataplaneCallStep(BaseStep[DataplaneCallParams, HttpBodyOutput]):
    """Fetch data from a data-plane endpoint using an EDR token.

    This is the far end of the DSP flow: ``do_dsp`` or ``initiate_transfer``
    publishes where the data is and how to authorize for it, and this step
    reads exactly those two variables.
    """

    params_model = DataplaneCallParams
    output_model = HttpBodyOutput

    async def execute(
        self, params: DataplaneCallParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[HttpBodyOutput]:
        url = params.resolved_url(context.get_variable(DATA_ADDRESS))
        token = params.edr_token or context.get_variable(EDR_TOKEN)
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
    verify: Optional[Any] = Field(
        default=None,
        description="TLS verification passed through to the SDK; None keeps its default.",
    )


def fetch_data_address(consumer: Any, transfer_id: Optional[str], verify: Any = None) -> Optional[dict]:
    """Fetch the EDR data address for a transfer, or ``None`` if it cannot be read.

    The one place that calls ``consumer.get_edr`` — ``connector/consumer/get_edr``
    and ``connector/consumer/initiate_transfer`` both resolve a ``transfer_id``
    and then call this. An unreachable connector is reported as "no data address"
    rather than raised: the caller still has whatever else it resolved (an EDR
    entry, a negotiation), and a 404/500 in the step's response is how a script
    asserts on the failure.
    """
    if not transfer_id:
        return None
    try:
        return consumer.get_edr(transfer_id=transfer_id, verify=verify)
    except ConnectionError:
        logger.warning("Failed to retrieve EDR data address for transfer %s", transfer_id)
        return None


@step("connector/consumer/get_edr")
class GetEdrStep(BaseStep[GetEdrParams, DataAddressPayload]):
    """Retrieve the EDR data address for a completed transfer.

    Publishes the same data-plane pair as ``initiate_transfer``, so it can stand
    in for that step when the transfer was started elsewhere — a PULL
    ``initiate_transfer`` resolves a ``negotiation_id`` down to a ``transfer_id``
    and then does exactly what this step does.
    """

    params_model = GetEdrParams
    output_model = DataAddressPayload
    exports_model = DataplaneExports

    async def execute(
        self, params: GetEdrParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[DataAddressPayload]:
        consumer = context.get_consumer_service()
        transfer_id = params.transfer_id or context.get_variable(TRANSFER_ID)
        url = context.get_consumer_endpoint_url("edrs", transfer_id, "dataaddress")

        edr = fetch_data_address(consumer, transfer_id, params.verify)

        return StepOutput(
            value=DataAddressPayload.of(edr),
            request=HttpRequest(method="GET", url=url),
            response=HttpResponse(status_code=200 if edr else 404, body=edr),
            exports=DataplaneExports(
                data_address=(edr or {}).get("endpoint"),
                edr_token=data_address_token(edr),
            ),
        )

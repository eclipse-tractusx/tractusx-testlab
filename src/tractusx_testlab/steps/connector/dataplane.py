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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Data-plane interaction steps — fetch data through EDR endpoint."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import http_client, sdk_call
from tractusx_testlab.steps.shared_models import (
    DataAddressPayload,
    HttpBodyOutput,
    HttpCallParams,
    StepParams,
    data_address_token,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import (
    DATAPLANE_URL,
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
    the transfer — every step publishes all of its return outputs, and the
    steps that end a transfer all return the ``dataplane_url``/``edr_token``
    pair under exactly these names.
    """

    dataplane_url: Any = Field(
        default=None,
        description=(
            "Data-plane URL, or a data address object to read it from; falls back "
            "to the 'dataplane_url' context variable."
        ),
    )
    path: str = Field(default="", description="Path appended to the data-plane URL.")
    edr_token: str | None = Field(
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
    returns where the data is and how to authorize for it, and this step
    reads exactly those two variables.
    """

    params_model = DataplaneCallParams
    output_model = HttpBodyOutput

    async def execute(
        self, params: DataplaneCallParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[HttpBodyOutput]:
        url = params.resolved_url(context.get_str(DATAPLANE_URL))
        token = params.edr_token or context.get_str(EDR_TOKEN)
        headers = {"Authorization": token, **params.headers}
        timeout = params.timeout_or(context.config.default_timeout_s)

        resp = await http_client.request(
            params.method, url, headers=headers, json=params.body, timeout=timeout
        )

        return StepOutput(
            value=HttpBodyOutput(http_client.body_of(resp)),
            request=HttpRequest(method=params.method, url=url, headers=headers, body=params.body),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=http_client.headers_of(resp),
                body=resp.text,
            ),
        )


# ---------------------------------------------------------------------------
# connector/consumer/get_edr
# ---------------------------------------------------------------------------


class GetEdrParams(StepParams):
    """Input contract of ``connector/consumer/get_edr``."""

    transfer_id: str | None = Field(
        default=None,
        description=(
            "Transfer process to read the EDR of; falls back to the 'transfer_id' context variable."
        ),
    )
    verify: Any | None = Field(
        default=None,
        description="TLS verification passed through to the SDK; None keeps its default.",
    )


async def fetch_data_address(
    consumer: Any, transfer_id: str | None, verify: Any = None
) -> dict | None:
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
        return await sdk_call.run(consumer.get_edr, transfer_id=transfer_id, verify=verify)
    except ConnectionError:
        logger.warning("Failed to retrieve EDR data address for transfer %s", transfer_id)
        return None


class EdrOutput(StepPayload):
    """Output contract of ``connector/consumer/get_edr``.

    The data-plane pair is lifted out of the document so it lands under the
    same names every transfer-completing step returns them under, and the full
    document stays alongside for assertions on its other keys.
    """

    dataplane_url: str | None = Field(
        default=None, description="Data-plane URL the negotiated data is fetched from."
    )
    edr_token: str | None = Field(
        default=None, description="Authorization token for that data-plane URL."
    )
    data_address: DataAddressPayload | None = Field(
        default=None, description="The full EDR data address document, unchanged."
    )


@step("connector/consumer/get_edr")
class GetEdrStep(BaseStep[GetEdrParams, EdrOutput]):
    """Retrieve the EDR data address for a completed transfer.

    Returns the same data-plane pair as ``initiate_transfer``, so it can stand
    in for that step when the transfer was started elsewhere — a PULL
    ``initiate_transfer`` resolves a ``negotiation_id`` down to a ``transfer_id``
    and then does exactly what this step does.
    """

    params_model = GetEdrParams
    output_model = EdrOutput

    async def execute(
        self, params: GetEdrParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[EdrOutput]:
        consumer = context.dataspace.consumer()
        transfer_id = params.transfer_id or context.get_str(TRANSFER_ID)
        url = context.dataspace.consumer_endpoint_url("edrs", transfer_id, "dataaddress")

        edr = await fetch_data_address(consumer, transfer_id, params.verify)

        value = None
        if edr is not None:
            value = EdrOutput(
                dataplane_url=edr.get("endpoint"),
                edr_token=data_address_token(edr),
                data_address=DataAddressPayload.of(edr),
            )
        return StepOutput(
            value=value,
            request=HttpRequest(method="GET", url=url),
            response=HttpResponse(status_code=200, body=edr),
        )

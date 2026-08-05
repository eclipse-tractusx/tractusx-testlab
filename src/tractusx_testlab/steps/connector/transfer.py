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

"""Data transfer step — resolves the EDR data address for a negotiated contract."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import (
    DataAddressPayload,
    DataplaneExports,
    StepParams,
    data_address_token,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import (
    DATA_ADDRESS,
    EDR_ENTRY,
    NEGOTIATION_ID,
    TRANSFER_ID,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


<<<<<<< HEAD
# ---------------------------------------------------------------------------
# connector/consumer/transfer_data
# ---------------------------------------------------------------------------


class TransferDataParams(StepParams):
    """Input contract of ``connector/consumer/transfer_data``."""

    negotiation_id: Optional[str] = Field(
        default=None,
        description=(
            "Negotiation to collect the EDR for; falls back to the "
            "'negotiation_id' context variable."
        ),
    )
    verify: Optional[Any] = Field(
        default=None,
        description="TLS verification passed through to the SDK; None keeps its default.",
    )


class TransferDataOutput(StepPayload):
    """Output contract of ``connector/consumer/transfer_data``.

    Everything is ``None`` when the negotiation produced no EDR — the step
    reports that as a 500 so a script can assert on it.
    """

    edr_entry: Optional[dict] = Field(
        default=None, description="The EDR entry the negotiation produced."
    )
    data_address: Optional[str] = Field(
        default=None, description="Data-plane URL the negotiated data is fetched from."
    )
    edr_token: Optional[str] = Field(
        default=None, description="Authorization token for that data-plane URL."
    )
    data_address_raw: Optional[DataAddressPayload] = Field(
        default=None,
        description="The full data address document, for assertions on its other keys.",
    )


class TransferDataExports(DataplaneExports):
    """Context variables published by ``connector/consumer/transfer_data``.

    Extends the shared data-plane pair with the transfer's own identifiers, and
    keeps ``data_address`` as an older spelling of ``dataplane_endpoint`` that
    existing scripts still read.
    """

    transfer_id: Optional[str] = Field(
        default=None, alias=TRANSFER_ID, description="ID of the transfer process."
    )
    edr_entry: Optional[dict] = Field(
        default=None, alias=EDR_ENTRY, description="The EDR entry the negotiation produced."
    )
    data_address: Optional[str] = Field(
        default=None, alias=DATA_ADDRESS, description="Older spelling of 'dataplane_endpoint'."
    )


@step("connector/consumer/transfer_data")
class TransferDataStep(BaseStep[TransferDataParams, TransferDataOutput]):
    """Collect the EDR for a negotiated contract and resolve its data address.

    This is what turns a finished negotiation into something
    ``connector/dataplane/http_request`` can call: it polls for the EDR entry,
    then asks the connector for the data address that entry points at.
    """

    params_model = TransferDataParams
    output_model = TransferDataOutput
    exports_model = TransferDataExports

    async def execute(
        self, params: TransferDataParams, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput[TransferDataOutput]:
=======
@step("connector/consumer/transfer_data")
class TransferDataStep(BaseStep):
    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
>>>>>>> 4151bc2 (Refactor step identifiers for consistency and clarity)
        consumer = context.get_consumer_service()
        url = context.get_consumer_endpoint_url("transfer_processes")

        negotiation_id = params.negotiation_id or context.get_variable(NEGOTIATION_ID)
        edr_entry = consumer.get_edr_entry(negotiation_id=negotiation_id, verify=params.verify)

        transfer_id = _transfer_id(edr_entry)
        data_address = _resolve_data_address(transfer_id, consumer, params.verify)
        endpoint = (data_address or {}).get("endpoint")
        auth_token = data_address_token(data_address)

        value = TransferDataOutput(
            edr_entry=edr_entry,
            data_address=endpoint,
            edr_token=auth_token,
            data_address_raw=data_address,
        )
        return StepOutput(
            value=value,
            request=HttpRequest(method="POST", url=url),
            response=HttpResponse(
                status_code=200 if edr_entry else 500,
                body={
                    "edr_entry": edr_entry,
                    "data_address": endpoint,
                    "edr_token": auth_token,
                    "data_address_raw": data_address,
                },
            ),
            exports=TransferDataExports(
                transfer_id=transfer_id,
                edr_entry=edr_entry,
                data_address=endpoint,
                dataplane_endpoint=endpoint,
                edr_token=auth_token,
            ),
        )


def _transfer_id(edr_entry: Optional[dict]) -> Optional[str]:
    """Read the transfer process ID from an EDR entry under either of its spellings."""
    if not edr_entry:
        return None
    return edr_entry.get("transferProcessId") or edr_entry.get("@id")


def _resolve_data_address(
    transfer_id: Optional[str], consumer: Any, verify: Any
) -> Optional[dict]:
    """Ask the connector for the data address a transfer points at.

    A connector that cannot be reached is reported as "no data address" rather
    than aborting the step: the EDR entry itself is still worth returning, and
    the 500 in the response says the transfer did not complete.
    """
    if not transfer_id:
        return None
    try:
        return consumer.get_edr(transfer_id=transfer_id, verify=verify)
    except ConnectionError:
        logger.warning("Failed to retrieve EDR data address for transfer %s", transfer_id)
        return None

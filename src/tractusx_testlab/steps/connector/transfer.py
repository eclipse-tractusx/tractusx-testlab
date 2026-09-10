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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Transfer step — starts a transfer and resolves what it produced."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator
from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition, StepExecutionError
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.connector._polling import (
    DEFAULT_MAX_WAIT,
    DEFAULT_POLL_INTERVAL,
    TRANSFER_TERMINAL,
    poll_until_terminal,
    read_entity,
)
from tractusx_testlab.steps.connector.dataplane import fetch_data_address
from tractusx_testlab.steps.shared_models import (
    DataAddressPayload,
    StepParams,
    data_address_token,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import (
    AGREEMENT_ID,
    NEGOTIATION_ID,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

#: The transfer the connector performs when the script does not ask for another.
PULL_TRANSFER_TYPE = "HttpData-PULL"


# ---------------------------------------------------------------------------
# connector/consumer/initiate_transfer
# ---------------------------------------------------------------------------


class InitiateTransferParams(StepParams):
    """Input contract of ``connector/consumer/initiate_transfer``.

    Which fields matter depends on ``transfer_type``.  A PULL transfer is
    resolved from the negotiation the consumer already ran, so it needs only
    ``negotiation_id``; a PUSH transfer is a request in its own right and needs
    the agreement to perform it under and the destination to push to.
    """

    transfer_type: str = Field(
        default=PULL_TRANSFER_TYPE,
        description=(
            "How the data moves: 'HttpData-PULL' (the consumer fetches it) or a "
            "'-PUSH' type such as 'HttpData-PUSH' or 'AmazonS3-PUSH'."
        ),
    )
    negotiation_id: str | None = Field(
        default=None,
        description=(
            "PULL only — negotiation to collect the EDR for; falls back to the "
            "'negotiation_id' context variable."
        ),
    )
    agreement_id: str | None = Field(
        default=None,
        description=(
            "PUSH only — contract agreement the transfer runs under; falls back "
            "to the 'agreement_id' context variable."
        ),
    )
    data_destination: dict | None = Field(
        default=None,
        description="PUSH only — the EDC data address the provider pushes to.",
    )
    counter_party_address: str = Field(
        default="",
        description=(
            "PUSH only — DSP endpoint of the provider; defaults to the bound SUT "
            "connector's 'dsp_url'."
        ),
    )
    max_wait: float = Field(
        default=DEFAULT_MAX_WAIT,
        description=(
            "Seconds to wait for the transfer to settle: for a PULL, until the "
            "EDR the negotiation started is written; for a PUSH, until the "
            "transfer reaches a final state."
        ),
    )
    poll_interval: float = Field(
        default=DEFAULT_POLL_INTERVAL,
        description="Seconds between two reads while waiting.",
    )
    verify: Any | None = Field(
        default=None,
        description="TLS verification passed through to the SDK; None keeps its default.",
    )

    @property
    def is_push(self) -> bool:
        """Whether this transfer pushes data rather than making it pullable."""
        return self.transfer_type.upper().endswith("-PUSH")

    @model_validator(mode="after")
    def _push_needs_a_destination(self) -> InitiateTransferParams:
        """A PUSH with nowhere to push to would start and then fail at the provider."""
        if self.is_push and not self.data_destination:
            raise ValueError(
                f"transfer_type {self.transfer_type!r} pushes data, so "
                "'data_destination' is required."
            )
        return self


class InitiateTransferOutput(StepPayload):
    """Output contract of ``connector/consumer/initiate_transfer``.

    A PUSH transfer fills in ``transfer_id`` and ``state`` alone: the data goes
    to the destination the request named, so there is no EDR to read back.
    """

    transfer_id: str | None = Field(default=None, description="ID of the transfer process.")
    state: str | None = Field(
        default=None,
        description="State the transfer settled at, e.g. 'STARTED' or 'COMPLETED'.",
    )
    edr_entry: dict | None = Field(
        default=None, description="PULL only — the EDR entry the negotiation produced."
    )
    dataplane_url: str | None = Field(
        default=None, description="PULL only — data-plane URL the data is fetched from."
    )
    edr_token: str | None = Field(
        default=None, description="PULL only — authorization token for that data-plane URL."
    )
    data_address: DataAddressPayload | None = Field(
        default=None,
        description="PULL only — the full data address document, for assertions on its other keys.",
    )


@step("connector/consumer/initiate_transfer")
class InitiateTransferStep(BaseStep[InitiateTransferParams, InitiateTransferOutput]):
    """Start a data transfer for a contract that has already been negotiated.

    A PULL transfer turns a finished negotiation into something
    ``connector/dataplane/http_request`` can call: it resolves ``negotiation_id``
    down to a ``transfer_id``, then does exactly what
    ``connector/consumer/get_edr`` does with one — the two steps share that
    lookup rather than each fetching the data address their own way.

    A PUSH transfer instead asks the connector to deliver the data to a
    destination of the script's choosing, and waits for that transfer to settle.
    """

    params_model = InitiateTransferParams
    output_model = InitiateTransferOutput

    async def execute(
        self, params: InitiateTransferParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[InitiateTransferOutput]:
        if params.is_push:
            return await self._push(params, context)
        return await self._pull(params, context)

    async def _pull(
        self, params: InitiateTransferParams, context: StepContext
    ) -> StepOutput[InitiateTransferOutput]:
        """Collect the EDR the negotiation produced and resolve its data address."""
        consumer = context.dataspace.consumer()
        negotiation_id = params.negotiation_id or context.get_str(NEGOTIATION_ID)
        edr_entry = await _await_edr_entry(consumer, negotiation_id, params, what=self.step_type)

        transfer_id = _transfer_id(edr_entry)
        data_address = await fetch_data_address(consumer, transfer_id, params.verify)
        endpoint = (data_address or {}).get("endpoint")

        # The EDR is written when the transfer starts, so by now it has a state
        # worth reporting and one read is enough.
        transfer = read_entity(
            getattr(consumer, "transfer_processes", None), transfer_id or "", params.verify
        )

        value = InitiateTransferOutput(
            transfer_id=transfer_id,
            state=(transfer or {}).get("state"),
            edr_entry=edr_entry,
            dataplane_url=endpoint,
            edr_token=data_address_token(data_address),
            data_address=DataAddressPayload.of(data_address),
        )
        return StepOutput(
            value=value,
            request=HttpRequest(
                method="POST", url=context.dataspace.consumer_endpoint_url("transfer_processes")
            ),
            response=HttpResponse(status_code=200, body=value.model_dump(mode="json")),
        )

    async def _push(
        self, params: InitiateTransferParams, context: StepContext
    ) -> StepOutput[InitiateTransferOutput]:
        """Ask the connector to deliver the data to the destination the script named."""
        consumer = context.dataspace.consumer()
        url = context.dataspace.consumer_endpoint_url("transfer_processes")
        request_model = ModelFactory.get_transfer_process_model(
            dataspace_version=consumer.dataspace_version,
            counter_party_address=(
                params.counter_party_address or context.infrastructure.sut.connector.dsp_url
            ),
            transfer_type=params.transfer_type,
            contract_id=params.agreement_id or context.get_str(AGREEMENT_ID),
            data_destination=params.data_destination or {},
        )
        response = consumer.transfer_processes.create(request_model)
        transfer_id = _created_id(response)

        transfer = await poll_until_terminal(
            getattr(consumer, "transfer_processes", None),
            transfer_id or "",
            TRANSFER_TERMINAL,
            max_wait=params.max_wait,
            poll_interval=params.poll_interval,
            what="connector/consumer/initiate_transfer",
            verify=params.verify,
        )

        value = InitiateTransferOutput(transfer_id=transfer_id, state=transfer.get("state"))
        return StepOutput(
            value=value,
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(
                status_code=getattr(response, "status_code", 500) if transfer_id else 500,
                body=value.model_dump(mode="json"),
            ),
        )


async def _await_edr_entry(
    consumer: Any, negotiation_id: str, params: InitiateTransferParams, *, what: str
) -> dict:
    """Wait for the EDR the negotiation's transfer writes, and return it.

    A FINALIZED negotiation is not yet an EDR. The EDR API starts a transfer
    process the moment the negotiation finalises, and the EDR is written only
    when that transfer reaches STARTED — a second or so later on a healthy
    connector. The step that waited for the negotiation therefore hands over
    an id whose EDR does not exist yet, and a single query here answered an
    empty list.

    While the EDR is missing the transfer process is what says why: it exists
    before the EDR does, and it carries the ``errorDetail`` when the provider
    turned the transfer down. It is read by the agreement id the negotiation
    settled on, so a terminated transfer fails the step at once instead of at
    the end of *max_wait*.

    Raises:
        StepExecutionError: if the transfer terminated, or the EDR never appeared.
    """
    deadline = time.monotonic() + params.max_wait
    agreement_id: str | None = None
    transfer: dict = {}
    while True:
        edr_entry = await sdk_call.run(
            consumer.get_edr_entry, negotiation_id=negotiation_id, verify=params.verify
        )
        if edr_entry:
            return edr_entry

        agreement_id = agreement_id or _agreement_id_of(consumer, negotiation_id, params.verify)
        if agreement_id:
            transfer = await _transfer_for(consumer, agreement_id, params.verify) or transfer
        state = str(transfer.get("state", ""))
        if state == "TERMINATED":
            raise StepExecutionError(
                what,
                f"the transfer the negotiation {negotiation_id} started was terminated "
                f"before it produced an EDR: {transfer.get('errorDetail') or 'no detail given'}",
            )

        if time.monotonic() + params.poll_interval > deadline:
            seen = f"transfer last seen {state!r}" if state else "no transfer process observed"
            raise StepExecutionError(
                what,
                f"the negotiation {negotiation_id} produced no EDR within "
                f"{params.max_wait}s ({seen}), so this PULL transfer has no "
                "data-plane address or token to hand on.",
            )
        await asyncio.sleep(params.poll_interval)


def _agreement_id_of(consumer: Any, negotiation_id: str, verify: Any) -> str | None:
    """The agreement id a finalised negotiation carries, or ``None`` if unreadable."""
    negotiation = read_entity(
        getattr(consumer, "contract_negotiations", None), negotiation_id, verify
    )
    return (negotiation or {}).get("contractAgreementId") or None


async def _transfer_for(consumer: Any, agreement_id: str, verify: Any) -> dict | None:
    """The transfer process running under *agreement_id*, or ``None`` if none yet."""
    try:
        transfer = await sdk_call.run(
            consumer.get_transfer_process, agreement_id=agreement_id, verify=verify
        )
    except Exception as exc:  # The EDR query decides; this read only explains.
        logger.debug("Could not read the transfer for agreement %s: %s", agreement_id, exc)
        return None
    return transfer if isinstance(transfer, dict) else None


def _transfer_id(edr_entry: dict | None) -> str | None:
    """Read the transfer process ID from an EDR entry under either of its spellings."""
    if not edr_entry:
        return None
    return edr_entry.get("transferProcessId") or edr_entry.get("@id")


def _created_id(response: Any) -> str | None:
    """Read the ``@id`` the connector answers a create request with."""
    try:
        body = response.json()
    except (AttributeError, ValueError):
        logger.error("Transfer process request returned no readable body")
        return None
    return body.get("@id") if isinstance(body, dict) else None

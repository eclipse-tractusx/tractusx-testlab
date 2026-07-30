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

"""DSP contract negotiation steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import (
    DSP_CONTRACT_AGREEMENT_ID,
    DSP_NEGOTIATION_CONSUMER_PID,
    DSP_NEGOTIATION_PROVIDER_PID,
    DSP_NEGOTIATION_STATE,
    DSP_OFFER,
)

from ._constants import DSPACE_AGREEMENT_ID, DSPACE_CONSUMER_PID, DSPACE_PROVIDER_PID, DSPACE_STATE

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/dsp/negotiate")
class DspNegotiateStep(BaseStep):
    """Send a DSP ContractRequestMessage directly to the provider.

    Params:
        service (str, optional): Named DSP_CONSUMER service to use.
        offer (dict, optional): ODRL Offer from catalog. Falls back to ``dsp_offer``.
        consumer_pid (str, optional): Consumer process ID. Auto-generated if omitted.
        callback_address (str, optional): Consumer DSP callback URL.

    Stores in context:
        dsp_negotiation_provider_pid: Provider-assigned process ID (``dspace:providerPid``).
        dsp_negotiation_consumer_pid: Consumer process ID (``dspace:consumerPid``).
        dsp_negotiation_state: Current negotiation state (``dspace:state``).
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition,
    ) -> StepOutput:
        import uuid

        dsp = context.get_dsp_consumer_service(params.get("service"))
        offer = params.get("offer") or context.get_variable(DSP_OFFER)
        consumer_pid = params.get("consumer_pid", f"urn:uuid:{uuid.uuid4()}")
        callback_address = params.get("callback_address")

        resp = dsp.initiate_negotiation(
            offer=offer,
            consumer_pid=consumer_pid,
            callback_address=callback_address,
        )

        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        # Extract and store DSP negotiation state for downstream steps
        if isinstance(body, dict):
            provider_pid = body.get(DSPACE_PROVIDER_PID)
            if provider_pid:
                context.set_variable(DSP_NEGOTIATION_PROVIDER_PID, provider_pid)
            c_pid = body.get(DSPACE_CONSUMER_PID)
            if c_pid:
                context.set_variable(DSP_NEGOTIATION_CONSUMER_PID, c_pid)
            state = body.get(DSPACE_STATE)
            if state:
                context.set_variable(DSP_NEGOTIATION_STATE, state)

        return StepOutput(
            value=body,
            request=HttpRequest(
                method="POST",
                url=f"{dsp.base_url}/negotiations/initial",
                body={"offer": offer, "consumer_pid": consumer_pid},
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
            ),
        )


@step("connector/consumer/dsp/get_negotiation")
class DspGetNegotiationStep(BaseStep):
    """Poll a DSP negotiation state by provider PID.

    Sends ``GET negotiations/{provider_pid}`` to retrieve the current
    negotiation process state. Used to wait for async negotiation to
    reach a target state (e.g., ``FINALIZED``, ``AGREED``).

    Params:
        service (str, optional): Named DSP_CONSUMER service to use.
        provider_pid (str, optional): Provider PID. Falls back to ``dsp_negotiation_provider_pid``.

    Stores in context:
        dsp_negotiation_state: Current negotiation state (``dspace:state``).
        contract_agreement_id: Agreement ID once negotiation is FINALIZED.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition,
    ) -> StepOutput:
        dsp = context.get_dsp_consumer_service(params.get("service"))
        provider_pid = params.get("provider_pid") or context.get_variable(
            DSP_NEGOTIATION_PROVIDER_PID,
        )

        resp = dsp.get_negotiation(provider_pid=provider_pid)

        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        if isinstance(body, dict):
            state = body.get(DSPACE_STATE)
            if state:
                context.set_variable(DSP_NEGOTIATION_STATE, state)
            agreement_id = body.get(DSPACE_AGREEMENT_ID)
            if agreement_id:
                context.set_variable(DSP_CONTRACT_AGREEMENT_ID, agreement_id)

        return StepOutput(
            value=body,
            request=HttpRequest(
                method="GET",
                url=f"{dsp.base_url}/negotiations/{provider_pid}",
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
            ),
        )

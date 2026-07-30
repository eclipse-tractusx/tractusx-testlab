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

"""DSP transfer process steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import (
    DSP_CONTRACT_AGREEMENT_ID,
    DSP_TRANSFER_CONSUMER_PID,
    DSP_TRANSFER_PROVIDER_PID,
    DSP_TRANSFER_STATE,
)

from ._constants import DSPACE_CONSUMER_PID, DSPACE_PROVIDER_PID, DSPACE_STATE

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/dsp/transfer_request")
class DspTransferRequestStep(BaseStep):
    """Send a DSP TransferRequestMessage directly to the provider.

    Params:
        service (str, optional): Named DSP_CONSUMER service to use.
        agreement_id (str, optional): Contract agreement ID. Falls back to ``contract_agreement_id``.
        format (str): Transfer type profile (e.g., ``HttpData-PULL``).
        consumer_pid (str, optional): Consumer process ID.
        callback_address (str, optional): Consumer DSP callback URL.
        data_address (dict, optional): Destination for PUSH transfers.

    Stores in context:
        dsp_transfer_provider_pid: Provider-assigned transfer process ID.
        dsp_transfer_consumer_pid: Consumer transfer process ID.
        dsp_transfer_state: Current transfer state.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition,
    ) -> StepOutput:
        import uuid

        dsp = context.get_dsp_consumer_service(params.get("service"))
        agreement_id = params.get("agreement_id") or context.get_variable(
            DSP_CONTRACT_AGREEMENT_ID,
        )
        resp = dsp.request_transfer(
            agreement_id=agreement_id,
            transfer_format=params.get("format", "HttpData-PULL"),
            consumer_pid=params.get("consumer_pid", f"urn:uuid:{uuid.uuid4()}"),
            callback_address=params.get("callback_address"),
            data_address=params.get("data_address"),
        )

        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        # Extract and store DSP transfer state for downstream steps
        if isinstance(body, dict):
            provider_pid = body.get(DSPACE_PROVIDER_PID)
            if provider_pid:
                context.set_variable(DSP_TRANSFER_PROVIDER_PID, provider_pid)
            c_pid = body.get(DSPACE_CONSUMER_PID)
            if c_pid:
                context.set_variable(DSP_TRANSFER_CONSUMER_PID, c_pid)
            state = body.get(DSPACE_STATE)
            if state:
                context.set_variable(DSP_TRANSFER_STATE, state)

        return StepOutput(
            value=body,
            request=HttpRequest(
                method="POST",
                url=f"{dsp.base_url}/transfers/request",
                body=params,
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
            ),
        )


@step("connector/consumer/dsp/get_transfer")
class DspGetTransferStep(BaseStep):
    """Poll a DSP transfer state by provider PID.

    Sends ``GET transfers/{provider_pid}`` to retrieve the current
    transfer process state. Used to wait for async transfer to
    reach a target state (e.g., ``STARTED``, ``COMPLETED``).

    Params:
        service (str, optional): Named DSP_CONSUMER service to use.
        provider_pid (str, optional): Provider PID. Falls back to ``dsp_transfer_provider_pid``.

    Stores in context:
        dsp_transfer_state: Current transfer state (``dspace:state``).
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition,
    ) -> StepOutput:
        dsp = context.get_dsp_consumer_service(params.get("service"))
        provider_pid = params.get("provider_pid") or context.get_variable(
            DSP_TRANSFER_PROVIDER_PID,
        )

        resp = dsp.get_transfer(provider_pid=provider_pid)

        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        if isinstance(body, dict):
            state = body.get(DSPACE_STATE)
            if state:
                context.set_variable(DSP_TRANSFER_STATE, state)

        return StepOutput(
            value=body,
            request=HttpRequest(
                method="GET",
                url=f"{dsp.base_url}/transfers/{provider_pid}",
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
            ),
        )

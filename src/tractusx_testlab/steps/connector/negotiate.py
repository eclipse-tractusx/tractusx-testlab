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

"""Contract negotiation step — direct DSP negotiation with the provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.steps.connector._dsp_consumer import _create_dsp_consumer
from tractusx_testlab.syntax.context_vars import CATALOG_POLICY, NEGOTIATION_ID

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/negotiate_contract")
class NegotiateContractStep(BaseStep):
    """Start a DSP contract negotiation directly with the provider."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        import uuid as _uuid

        counter_party_address = params.get("counter_party_address") or context.get_variable("provider_address", "")
        offer = params.get("policy") or params.get("offer_id") or context.get_variable(CATALOG_POLICY)
        consumer_pid = params.get("consumer_pid", f"urn:uuid:{_uuid.uuid4()}")

        # Use DSP protocol directly (same as catalog step) to avoid management API mismatch.
        dsp_consumer = _create_dsp_consumer(counter_party_address)
        resp = dsp_consumer.initiate_negotiation(
            offer=offer,
            consumer_pid=consumer_pid,
            callback_address=params.get("callback_address"),
        )

        url = f"{counter_party_address}/negotiations/request"
        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        agreement_id = None
        negotiation_id = None
        if isinstance(body, dict):
            negotiation_id = body.get("@id")
            agreement = body.get("dspace:agreement", {})
            if isinstance(agreement, dict):
                agreement_id = agreement.get("@id")

        if negotiation_id:
            context.set_variable(NEGOTIATION_ID, negotiation_id)
        if agreement_id:
            context.set_variable("agreement_id", agreement_id)

        return StepOutput(
            value={"negotiation_id": negotiation_id, "agreement_id": agreement_id},
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(
                status_code=resp.status_code,
                body=body,
            ),
        )

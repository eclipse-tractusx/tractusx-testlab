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

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import CATALOG_POLICY, CATALOG_TARGET, NEGOTIATION_ID

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/negotiate", aliases=["negotiate_contract", "negotiate"])
class NegotiateContractStep(BaseStep):
    """Start an EDR contract negotiation with the provider via the SDK."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        consumer = context.get_consumer_service()
        counter_party_address = params.get("counter_party_address") or context.get_variable("provider_address", "")
        counter_party_id = params.get("counter_party_id") or context.get_variable("provider_bpnl", "")
        target = params.get("target") or context.get_variable(CATALOG_TARGET)
        policy = params.get("policy") or context.get_variable(CATALOG_POLICY)

        negotiation_id = consumer.start_edr_negotiation(
            counter_party_id=counter_party_id,
            counter_party_address=counter_party_address,
            target=target,
            policy=policy,
        )

        if negotiation_id:
            context.set_variable(NEGOTIATION_ID, negotiation_id)

        url = f"{counter_party_address}/v3/edrs"
        value = {"negotiation_id": negotiation_id}
        return StepOutput(
            value=value,
            request=HttpRequest(method="POST", url=url, body=params),
            response=HttpResponse(status_code=200 if negotiation_id else 500, body=value),
        )

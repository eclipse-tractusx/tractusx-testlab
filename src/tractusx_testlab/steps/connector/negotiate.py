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

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import CounterPartyParams
from tractusx_testlab.steps.base import BaseStep, StepExports, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import CATALOG_POLICY, CATALOG_TARGET, NEGOTIATION_ID

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# connector/consumer/negotiate_contract
# ---------------------------------------------------------------------------


class NegotiateContractParams(CounterPartyParams):
    """Input contract of ``connector/consumer/negotiate_contract``.

    Every field falls back to what an earlier catalog step published, so a
    script that ran ``query_catalog_by_asset_id`` first can leave them all out.
    """

    target: Optional[Any] = Field(
        default=None,
        description=(
            "Asset ID to negotiate for; falls back to the 'catalog_target' "
            "context variable."
        ),
    )
    policy: Optional[Any] = Field(
        default=None,
        description=(
            "ODRL policy to negotiate under; falls back to the 'catalog_policy' "
            "context variable."
        ),
    )


class NegotiationOutput(StepPayload):
    """Output contract of ``connector/consumer/negotiate_contract``."""

    negotiation_id: Optional[str] = Field(
        default=None, description="ID of the started negotiation."
    )


class NegotiationExports(StepExports):
    """Context variables published by ``connector/consumer/negotiate_contract``."""

    negotiation_id: Optional[str] = Field(
        default=None,
        alias=NEGOTIATION_ID,
        description="ID the transfer step polls for the resulting EDR.",
    )


@step("connector/consumer/negotiate_contract")
class NegotiateContractStep(BaseStep[NegotiateContractParams, NegotiationOutput]):
    """Start an EDR contract negotiation with the provider via the SDK.

    Returns as soon as the negotiation is accepted — it does not wait for it to
    finish; ``transfer_data`` is what polls for the resulting EDR.
    """

    params_model = NegotiateContractParams
    output_model = NegotiationOutput
    exports_model = NegotiationExports

    async def execute(
        self,
        params: NegotiateContractParams,
        context: "StepContext",
        definition: StepDefinitionV2,
    ) -> StepOutput[NegotiationOutput]:
        consumer = context.get_consumer_service()
        counter_party_address = params.counter_party_address or context.get_variable(
            "provider_address", ""
        )
        counter_party_id = params.counter_party_id or context.get_variable("provider_bpnl", "")

        negotiation_id = consumer.start_edr_negotiation(
            counter_party_id=counter_party_id,
            counter_party_address=counter_party_address,
            target=params.target or context.get_variable(CATALOG_TARGET),
            policy=params.policy or context.get_variable(CATALOG_POLICY),
        )

        url = context.get_consumer_endpoint_url("edrs")
        return StepOutput(
            value=NegotiationOutput(negotiation_id=negotiation_id),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(
                status_code=200 if negotiation_id else 500,
                body={"negotiation_id": negotiation_id},
            ),
            exports=NegotiationExports(negotiation_id=negotiation_id),
        )

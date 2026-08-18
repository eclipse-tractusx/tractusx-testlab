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

"""Contract negotiation step — direct DSP negotiation with the provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition, StepExecutionError
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.connector._polling import (
    DEFAULT_MAX_WAIT,
    DEFAULT_POLL_INTERVAL,
    NEGOTIATION_TERMINAL,
    poll_until_terminal,
)
from tractusx_testlab.steps.shared_models import CounterPartyParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import (
    CATALOG_ASSET_ID,
    CATALOG_POLICY,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# connector/consumer/negotiate
# ---------------------------------------------------------------------------


class NegotiateParams(CounterPartyParams):
    """Input contract of ``connector/consumer/negotiate``.

    Every field falls back to what an earlier catalog step published, so a
    script that ran ``query_catalog_by_asset_id`` first can leave them all out.
    """

    asset_id: Any | None = Field(
        default=None,
        description=(
            "Asset ID to negotiate for; falls back to the 'catalog_asset_id' "
            "context variable."
        ),
    )
    policy: Any | None = Field(
        default=None,
        description=(
            "ODRL policy to negotiate under; falls back to the 'catalog_policy' "
            "context variable."
        ),
    )
    max_wait: float = Field(
        default=DEFAULT_MAX_WAIT,
        description="Seconds to wait for the negotiation to reach a final state.",
    )
    poll_interval: float = Field(
        default=DEFAULT_POLL_INTERVAL,
        description="Seconds between two negotiation state reads.",
    )


class NegotiationOutput(StepPayload):
    """Output contract of ``connector/consumer/negotiate``."""

    negotiation_id: str | None = Field(
        default=None, description="ID of the started negotiation."
    )
    agreement_id: str | None = Field(
        default=None,
        description="ID of the contract agreement, once the negotiation finalised.",
    )
    state: str | None = Field(
        default=None,
        description="State the negotiation settled at, e.g. 'FINALIZED' or 'TERMINATED'.",
    )


@step("connector/consumer/negotiate")
class NegotiateStep(BaseStep[NegotiateParams, NegotiationOutput]):
    """Negotiate a contract with the provider and wait for the outcome.

    The SDK starts the negotiation and answers with its ID straight away; this
    step then polls the negotiation until it finalises or terminates, so what it
    returns is the settled outcome rather than "accepted for processing".
    """

    params_model = NegotiateParams
    output_model = NegotiationOutput

    async def execute(
        self,
        params: NegotiateParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[NegotiationOutput]:
        consumer = context.dataspace.consumer()
        counter_party_address = params.counter_party_address or context.get_str(
            "provider_address"
        )
        counter_party_id = params.counter_party_id or context.get_str("provider_bpnl")

        negotiation_id = await sdk_call.run(consumer.start_edr_negotiation,
            counter_party_id=counter_party_id,
            counter_party_address=counter_party_address,
            # `get_variable`, not `get_str`: the SDK is handed the absence as
            # `None`, and an empty string would say a target was named.
            target=params.asset_id or context.get_variable(CATALOG_ASSET_ID),
            policy=params.policy or context.get_variable(CATALOG_POLICY),
        )

        negotiation = await poll_until_terminal(
            getattr(consumer, "contract_negotiations", None),
            negotiation_id or "",
            NEGOTIATION_TERMINAL,
            max_wait=params.max_wait,
            poll_interval=params.poll_interval,
            what="connector/consumer/negotiate",
        )
        agreement_id = negotiation.get("contractAgreementId")
        state = negotiation.get("state")

        if not negotiation_id:
            raise StepExecutionError(
                self.step_type,
                "the connector accepted the request but returned no negotiation id, "
                "so there is nothing to observe.",
            )

        value = NegotiationOutput(
            negotiation_id=negotiation_id, agreement_id=agreement_id, state=state
        )
        url = context.dataspace.consumer_endpoint_url("edrs")
        return StepOutput(
            value=value,
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(
                status_code=200,
                body=value.model_dump(mode="json"),
            ),
        )

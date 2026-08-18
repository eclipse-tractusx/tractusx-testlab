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

"""Full DSP flow steps — thin wrappers over the SDK ``do_dsp`` helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition, StepExecutionError
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.shared_models import (
    CounterPartyParams,
    FilterExpressionParams,
    StepParams,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

#: ``dct:type`` the Catena-X standards mark a Digital Twin Registry asset with.
DTR_DCT_TYPE = "https://w3id.org/catenax/taxonomy#DigitalTwinRegistry"


class DspFlowOutput(StepPayload):
    """What every DSP flow step hands back: where the data is, and the token for it.

    Both fields are ``None`` when the flow did not complete — the step reports
    that as a 500 rather than raising, so a script can assert on it.
    """

    dataplane_url: str | None = Field(
        default=None, description="Data-plane URL the negotiated data is fetched from."
    )
    edr_token: str | None = Field(
        default=None, description="Authorization token for that data-plane URL."
    )


# ---------------------------------------------------------------------------
# connector/consumer/do_dsp
# ---------------------------------------------------------------------------


class DoDspParams(CounterPartyParams, FilterExpressionParams):
    """Input contract of ``connector/consumer/do_dsp``."""

    expected_policies: list[dict] = Field(
        default_factory=list,
        description="ODRL policies the negotiation is allowed to accept.",
    )


@step("connector/consumer/do_dsp")
class DoDspStep(BaseStep[DoDspParams, DspFlowOutput]):
    """Run the full DSP flow (catalog → negotiation → transfer) via the SDK.

    Returns the resulting data-plane address so
    ``connector/dataplane/http_request`` can fetch the data without any further
    wiring.
    """

    params_model = DoDspParams
    output_model = DspFlowOutput

    async def execute(
        self, params: DoDspParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[DspFlowOutput]:
        consumer = context.dataspace.consumer()
        endpoint, token = await sdk_call.run(consumer.do_dsp,
            counter_party_id=params.counter_party_id,
            counter_party_address=params.counter_party_address,
            filter_expression=params.sdk_filter_expression(),
            policies=params.expected_policies,
        )
        return _build_output(self.step_type, context, params, endpoint, token)


# ---------------------------------------------------------------------------
# connector/consumer/do_dsp_with_bpnl
# ---------------------------------------------------------------------------


class DoDspWithBpnlParams(FilterExpressionParams):
    """Input contract of ``connector/consumer/do_dsp_with_bpnl``.

    Unlike ``do_dsp``, the optional fields stay ``None`` rather than defaulting
    to empty: the SDK reads ``None`` as "no preference" and an empty list as
    "match nothing".
    """

    bpnl: str = Field(description="BPN used to discover the counter-party's connector.")
    counter_party_address: str | None = Field(
        default=None,
        description="DSP endpoint; when omitted it is resolved from the BPN by discovery.",
    )
    expected_policies: list[dict] | None = Field(
        default=None,
        description="ODRL policies the negotiation is allowed to accept.",
    )


@step("connector/consumer/do_dsp_with_bpnl")
class DoDspWithBpnlStep(BaseStep[DoDspWithBpnlParams, DspFlowOutput]):
    """Run the full DSP flow using BPNL-based connector discovery via the SDK.

    Returns the same data-plane address as ``do_dsp``.
    """

    params_model = DoDspWithBpnlParams
    output_model = DspFlowOutput

    async def execute(
        self, params: DoDspWithBpnlParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[DspFlowOutput]:
        consumer = context.dataspace.consumer()
        endpoint, token = await sdk_call.run(consumer.do_dsp_with_bpnl,
            bpnl=params.bpnl,
            counter_party_address=params.counter_party_address,
            filter_expression=params.sdk_filter_expression() or None,
            policies=params.expected_policies,
        )
        return _build_output(self.step_type, context, params, endpoint, token)


# ---------------------------------------------------------------------------
# connector/discover/digital-twin-registry/auth
# ---------------------------------------------------------------------------


class DiscoverDtrAuthParams(CounterPartyParams):
    """Input contract of ``connector/discover/digital-twin-registry/auth``.

    ``expected_policies`` stays ``None`` rather than defaulting to empty: the
    SDK reads ``None`` as "no preference" and an empty list as "match nothing".
    """

    dct_type: str = Field(
        default=DTR_DCT_TYPE,
        description="`dct:type` the registry asset is offered under in the catalog.",
    )
    expected_policies: list[dict] | None = Field(
        default=None,
        description="ODRL policies the negotiation is allowed to accept.",
    )


@step("connector/discover/digital-twin-registry/auth")
class DiscoverDtrAuthStep(BaseStep[DiscoverDtrAuthParams, DspFlowOutput]):
    """Get authorization to a counterparty's Digital Twin Registry.

    Finds the registry asset in the counterparty's catalog by its standard
    ``dct:type``, negotiates it, and publishes the resulting ``dataplane_url``
    and ``edr_token`` — exactly what the
    ``digital-twin-registry/consumer/dataplane/*`` steps read.
    """

    params_model = DiscoverDtrAuthParams
    output_model = DspFlowOutput

    async def execute(
        self,
        params: DiscoverDtrAuthParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DspFlowOutput]:
        consumer = context.dataspace.consumer()
        endpoint, token = await sdk_call.run(consumer.do_dsp_by_dct_type,
            counter_party_id=params.counter_party_id,
            counter_party_address=params.counter_party_address,
            dct_type=params.dct_type,
            policies=params.expected_policies,
        )
        return _build_output(self.step_type, context, params, endpoint, token)


def _build_output(
    step_type: str,
    context: StepContext,
    params: StepParams,
    endpoint: str | None,
    token: str | None,
) -> StepOutput[DspFlowOutput]:
    """Report the data-plane address every flow step ends at.

    A flow that produced no endpoint did not achieve what the step declares, so
    it fails rather than reporting a 500 the counterpart never sent — the code
    was invented, and nothing downstream read it.
    """
    if not endpoint:
        raise StepExecutionError(
            step_type,
            "the DSP flow completed without a data-plane endpoint, so there is "
            "nothing for a later step to pull data from.",
        )
    value = DspFlowOutput(dataplane_url=endpoint, edr_token=token)
    url = context.dataspace.consumer_endpoint_url("edrs")
    return StepOutput(
        value=value,
        request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
        response=HttpResponse(
            status_code=200,
            body=value.model_dump(mode="json"),
        ),
    )

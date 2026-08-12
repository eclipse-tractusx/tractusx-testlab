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

"""Full DSP flow steps — thin wrappers over the SDK ``do_dsp`` helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import (
    CounterPartyParams,
    DataplaneExports,
    FilterExpressionParams,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class DspFlowOutput(StepPayload):
    """What both DSP flow steps hand back: where the data is, and the token for it.

    Both fields are ``None`` when the flow did not complete — the step reports
    that as a 500 rather than raising, so a script can assert on it.
    """

    endpoint: Optional[str] = Field(
        default=None, description="Data-plane URL the negotiated data is fetched from."
    )
    token: Optional[str] = Field(
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

    Publishes the resulting data-plane address so
    ``connector/dataplane/http_request`` can fetch the data without any further
    wiring.
    """

    params_model = DoDspParams
    output_model = DspFlowOutput
    exports_model = DataplaneExports

    async def execute(
        self, params: DoDspParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[DspFlowOutput]:
        consumer = context.get_consumer_service()
        endpoint, token = consumer.do_dsp(
            counter_party_id=params.counter_party_id,
            counter_party_address=params.counter_party_address,
            filter_expression=params.sdk_filter_expression(),
            policies=params.expected_policies,
        )
        return _build_output(context, params, endpoint, token)


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
    counter_party_address: Optional[str] = Field(
        default=None,
        description="DSP endpoint; when omitted it is resolved from the BPN by discovery.",
    )
    expected_policies: Optional[list[dict]] = Field(
        default=None,
        description="ODRL policies the negotiation is allowed to accept.",
    )


@step("connector/consumer/do_dsp_with_bpnl")
class DoDspWithBpnlStep(BaseStep[DoDspWithBpnlParams, DspFlowOutput]):
    """Run the full DSP flow using BPNL-based connector discovery via the SDK.

    Publishes the same data-plane address as ``do_dsp``.
    """

    params_model = DoDspWithBpnlParams
    output_model = DspFlowOutput
    exports_model = DataplaneExports

    async def execute(
        self, params: DoDspWithBpnlParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[DspFlowOutput]:
        consumer = context.get_consumer_service()
        endpoint, token = consumer.do_dsp_with_bpnl(
            bpnl=params.bpnl,
            counter_party_address=params.counter_party_address,
            filter_expression=params.sdk_filter_expression() or None,
            policies=params.expected_policies,
        )
        return _build_output(context, params, endpoint, token)


def _build_output(
    context: "StepContext",
    params: FilterExpressionParams,
    endpoint: Optional[str],
    token: Optional[str],
) -> StepOutput[DspFlowOutput]:
    """Report the data-plane address both flow steps end at."""
    value = DspFlowOutput(endpoint=endpoint, token=token)
    url = context.get_consumer_endpoint_url("edrs")
    return StepOutput(
        value=value,
        request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
        response=HttpResponse(
            status_code=200 if endpoint else 500,
            body={"endpoint": endpoint, "token": token},
        ),
        exports=DataplaneExports(data_address=endpoint, edr_token=token),
    )

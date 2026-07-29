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

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import DATAPLANE_ENDPOINT, EDR_TOKEN

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/do_dsp", aliases=["do_dsp"])
class DoDspStep(BaseStep):
    """Run the full DSP flow (catalog → negotiation → transfer) via the SDK."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        consumer = context.get_consumer_service()
        endpoint, token = consumer.do_dsp(
            counter_party_id=params["counter_party_id"],
            counter_party_address=params["counter_party_address"],
            filter_expression=params.get("filter_expression", []),
            policies=params.get("policies", []),
        )
        return _build_output(context, params, endpoint, token)


@step("connector/consumer/do_dsp_with_bpnl", aliases=["do_dsp_with_bpnl"])
class DoDspWithBpnlStep(BaseStep):
    """Run the full DSP flow using BPNL-based connector discovery via the SDK."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinitionV2) -> StepOutput:
        consumer = context.get_consumer_service()
        endpoint, token = consumer.do_dsp_with_bpnl(
            bpnl=params["bpnl"],
            counter_party_address=params.get("counter_party_address"),
            filter_expression=params.get("filter_expression"),
            policies=params.get("policies"),
        )
        return _build_output(context, params, endpoint, token)


def _build_output(
    context: "StepContext", params: dict, endpoint: str | None, token: str | None,
) -> StepOutput:
    """Store the dataplane endpoint and EDR token in context and return a uniform output."""
    if endpoint:
        context.set_variable(DATAPLANE_ENDPOINT, endpoint)
    if token:
        context.set_variable(EDR_TOKEN, token)

    value = {"endpoint": endpoint, "token": token}
    url = f"{context.get_consumer_base_url()}/v3/edrs"
    return StepOutput(
        value=value,
        request=HttpRequest(method="POST", url=url, body=params),
        response=HttpResponse(status_code=200 if endpoint else 500, body=value),
    )

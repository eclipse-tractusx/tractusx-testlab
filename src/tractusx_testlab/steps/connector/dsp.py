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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Full DSP flow steps — single-call catalog→negotiate→transfer→EDR."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import DATAPLANE_ENDPOINT, EDR_TOKEN

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/dsp/do_dsp")
class DoDspStep(BaseStep):
    """Full DSP flow: catalog → negotiate → transfer → EDR in one step."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        consumer = context.get_consumer_service()
        url = f"{context.get_consumer_base_url()}"

        endpoint, token = consumer.do_dsp(
            counter_party_id=params["counter_party_id"],
            counter_party_address=params["counter_party_address"],
            filter_expression=params.get("filter_expression", []),
            policies=params.get("policies"),
            max_wait=params.get("max_wait", 60),
            poll_interval=params.get("poll_interval", 1),
        )

        context.set_variable(DATAPLANE_ENDPOINT, endpoint)
        context.set_variable(EDR_TOKEN, token)

        return StepOutput(
            value={"endpoint": endpoint, "token_prefix": token[:10] + "..." if token else None},
            request=HttpRequest(method="POST", url=url),
            response=HttpResponse(status_code=200, body={"endpoint": endpoint}),
        )


@step("connector/consumer/dsp/do_dsp_with_bpnl")
class DoDspWithBpnlStep(BaseStep):
    """Full DSP flow via BPNL: discover → catalog → negotiate → transfer → EDR."""

    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        consumer = context.get_consumer_service()
        url = f"{context.get_consumer_base_url()}"

        endpoint, token = consumer.do_dsp_with_bpnl(
            bpnl=params.get("bpnl") or params.get("counter_party_id"),
            counter_party_address=params.get("counter_party_address"),
            filter_expression=params.get("filter_expression", []),
            policies=params.get("policies"),
            max_wait=params.get("max_wait", 60),
            poll_interval=params.get("poll_interval", 1),
        )

        context.set_variable(DATAPLANE_ENDPOINT, endpoint)
        context.set_variable(EDR_TOKEN, token)

        return StepOutput(
            value={"endpoint": endpoint, "token_prefix": token[:10] + "..." if token else None},
            request=HttpRequest(method="POST", url=url),
            response=HttpResponse(status_code=200, body={"endpoint": endpoint}),
        )

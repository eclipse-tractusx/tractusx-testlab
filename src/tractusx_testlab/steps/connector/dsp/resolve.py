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

"""DSP DID resolution step."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("connector/consumer/dsp/resolve_did")
class DspResolveDidStep(BaseStep):
    """Resolve a DID document via HTTP.

    Params:
        did_url (str): The DID URL to resolve.
        timeout (float, optional): Request timeout.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinition,
    ) -> StepOutput:
        import httpx

        did_url = params["did_url"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(did_url, timeout=params.get("timeout", 30.0))

        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = resp.text

        return StepOutput(
            value=body,
            request=HttpRequest(method="GET", url=did_url),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
            ),
        )

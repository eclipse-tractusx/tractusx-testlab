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

"""UploadBackendDataStep — uploads sample data to the backend under a unique UUID path."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import BACKEND_URL
import httpx

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext
import uuid

@step("industry/submodel/upload_backend_data", aliases=["upload_backend_data"])
class UploadBackendDataStep(BaseStep):
    """Upload sample data to the backend under a unique UUID path.

    Generates a unique ``/urn:uuid:<uuid4>`` path so that each test run
    gets its own backend resource — exactly like the TCK does.

    Params:
        backend_base_url (str): Backend base URL (without UUID suffix).
        data (any): Payload to upload (sent as JSON).
        headers (dict): Optional extra headers.

    Stores in context:
        ``backend_url`` — the full backend URL with the unique path.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput:
        base = params["backend_base_url"].rstrip("/")
        unique_url = f"{base}/urn:uuid:{uuid.uuid4()}"
        data = params.get("data", {"test": True})
        headers = {"Content-Type": "application/json", **(params.get("headers") or {})}
        timeout = params.get("timeout", context.config.default_timeout_s)

        req = HttpRequest(method="POST", url=unique_url, headers=headers, body=data)

        async with httpx.AsyncClient() as client:
            resp = await client.post(unique_url, json=data, headers=headers, timeout=timeout)

        # Store the unique URL so subsequent steps can reference it
        context.set_variable(BACKEND_URL, unique_url)

        try:
            resp_body = resp.json()
        except (ValueError, TypeError):
            resp_body = resp.text

        return StepOutput(
            value={"backend_url": unique_url, "response": resp_body},
            request=req,
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp_body,
            ),
        )
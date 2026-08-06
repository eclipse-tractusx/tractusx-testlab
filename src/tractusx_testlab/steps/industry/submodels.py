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

from typing import TYPE_CHECKING, Any

import httpx
from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import HttpTransportParams
from tractusx_testlab.steps.base import BaseStep, StepExports, StepOutput, StepPayload
from tractusx_testlab.syntax.context_vars import BACKEND_URL

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

import uuid


class UploadBackendDataParams(HttpTransportParams):
    """Input contract of ``submodels/upload``.

    Only the transport half of an HTTP call: the step always POSTs to a URL it
    generates itself, so a ``method`` or ``url`` input would be a knob that
    does nothing.
    """

    backend_base_url: str = Field(description="Backend base URL, without the UUID suffix.")
    data: Any = Field(
        default_factory=lambda: {"test": True},
        description="Payload to upload, sent as JSON.",
    )


class UploadBackendDataOutput(StepPayload):
    """Output contract of ``submodels/upload``."""

    backend_url: str = Field(description="Full backend URL the data was uploaded to.")
    response: Any = Field(
        default=None, description="Backend response body, parsed as JSON when it is JSON."
    )


class UploadBackendDataExports(StepExports):
    """Context variables published by ``submodels/upload``."""

    backend_url: str = Field(
        alias=BACKEND_URL,
        description="Full backend URL, for the asset that will point at this data.",
    )


@step("submodels/upload")
class UploadBackendDataStep(BaseStep[UploadBackendDataParams, UploadBackendDataOutput]):
    """Upload sample data to the backend under a unique UUID path.

    Each run gets its own ``/urn:uuid:<uuid4>`` resource — exactly like the TCK
    does — so repeated runs never collide, and the resulting URL is published
    as ``backend_url`` for the asset that will point at it.
    """

    params_model = UploadBackendDataParams
    output_model = UploadBackendDataOutput
    exports_model = UploadBackendDataExports

    async def execute(
        self,
        params: UploadBackendDataParams,
        context: "StepContext",
        definition: StepDefinitionV2,
    ) -> StepOutput[UploadBackendDataOutput]:
        unique_url = f"{params.backend_base_url.rstrip('/')}/urn:uuid:{uuid.uuid4()}"
        headers = {"Content-Type": "application/json", **params.headers}
        timeout = params.timeout_or(context.config.default_timeout_s)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                unique_url, json=params.data, headers=headers, timeout=timeout
            )

        try:
            resp_body = resp.json()
        except (ValueError, TypeError):
            resp_body = resp.text

        return StepOutput(
            value=UploadBackendDataOutput(backend_url=unique_url, response=resp_body),
            request=HttpRequest(
                method="POST", url=unique_url, headers=headers, body=params.data
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp_body,
            ),
            exports=UploadBackendDataExports(backend_url=unique_url),
        )

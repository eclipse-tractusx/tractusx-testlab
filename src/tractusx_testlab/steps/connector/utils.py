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

"""Utility steps — generic HTTP and backend data helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests
from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import HttpBodyOutput, HttpCallParams
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class HttpRequestParams(HttpCallParams):
    """Input contract of ``http/http_request``."""

    url: str = Field(description="Target URL.")
    query_params: dict[str, str] = Field(
        default_factory=dict,
        description="Query string parameters appended to the URL.",
    )


@step("http/http_request")
class HttpRequestStep(BaseStep[HttpRequestParams, HttpBodyOutput]):
    """Execute a plain HTTP request.

    Useful for backend data upload/delete or any ad-hoc HTTP call during a test
    flow.  The output is the response body itself, so a JSON object response is
    published across context variables one per top-level key — the same way
    every step publishes its return outputs.
    """

    params_model = HttpRequestParams
    output_model = HttpBodyOutput

    async def execute(
        self, params: HttpRequestParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[HttpBodyOutput]:
        timeout = params.timeout_or(context.config.default_timeout_s)
        payload = (
            {"data": params.body} if isinstance(params.body, str) else {"json": params.body}
        )
        resp = requests.request(
            params.method,
            params.url,
            headers=params.headers,
            params=params.query_params or None,
            timeout=timeout,
            **payload,
        )

        try:
            resp_body = resp.json()
        except (ValueError, TypeError):
            resp_body = resp.text

        return StepOutput(
            value=HttpBodyOutput(resp_body),
            request=HttpRequest(
                method=params.method,
                url=resp.url,
                headers=params.headers,
                body=params.body,
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp_body,
            ),
        )
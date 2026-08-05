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

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


@step("http/http_request")
class HttpRequestStep(BaseStep):
    """Execute a plain HTTP request.

    Useful for backend data upload/delete or any ad-hoc HTTP call
    during a test flow.

    Params:
        method (str): HTTP method (GET, POST, PUT, DELETE). Default: GET.
        url (str): Target URL.
        body (any): Request body (sent as JSON for dicts, as raw text for strings).
        headers (dict): Extra HTTP headers.
        timeout (float): Request timeout in seconds.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput:
        method = params.get("method", "GET").upper()
        url = params["url"]
        body = params.get("body")
        headers = params.get("headers") or {}
        timeout = params.get("timeout", context.config.default_timeout_s)

        req = HttpRequest(method=method, url=url, headers=headers, body=body)

        if isinstance(body, str):
            resp = requests.request(
                method, url, data=body, headers=headers, timeout=timeout
            )
        else:
            resp = requests.request(
                method, url, json=body, headers=headers, timeout=timeout
            )

        try:
            resp_body = resp.json()
        except (ValueError, TypeError):
            resp_body = resp.text

        # Auto-store response body fields in context for downstream access
        if isinstance(resp_body, dict):
            for key, val in resp_body.items():
                context.set_variable(key, val)
        context.set_variable("status_code", resp.status_code)

        return StepOutput(
            value=resp_body,
            request=req,
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp_body,
            ),
        )
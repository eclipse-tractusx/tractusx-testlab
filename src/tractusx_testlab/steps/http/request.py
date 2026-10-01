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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Utility steps — generic HTTP and backend data helpers.

``http/http_request`` is the one step a credential handle may be handed to, and
only as the whole value of a header: ``headers: { x-api-key:
"${{ infrastructure.engine.connector.api_key }}" }``. The handle is released at
send time, for a request to the origin of the binding it came from and only
when the run releases that side (``TestlabConfig.credential_release``); the
recorded request carries ``***`` in its place.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field, PrivateAttr

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.security.credentials import Credential
from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.shared_models import HttpBodyOutput, HttpCallParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class HttpRequestParams(HttpCallParams):
    """Input contract of ``http/http_request``."""

    url: str = Field(description="Target URL.")
    query_params: dict[str, str] = Field(
        default_factory=dict,
        description="Query string parameters appended to the URL.",
    )

    #: Headers whose value is a credential handle, kept out of ``headers`` —
    #: which holds ``***`` for them — until the step releases them.
    _credentials: dict[str, Credential] = PrivateAttr(default_factory=dict)

    def wire_headers(self, released: frozenset[str] | set[str]) -> dict[str, str]:
        """The headers as sent, every credential released for :attr:`url` or refused."""
        return {
            **self.headers,
            **{
                name: credential.reveal_for(self.url, released)
                for name, credential in self._credentials.items()
            },
        }


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

    #: The ``with:`` keys whose values may each be a whole credential reference.
    credential_params: ClassVar[frozenset[str]] = frozenset({"headers"})

    @classmethod
    def bind_params(cls, raw_params: dict) -> Any:
        """Validate the parameters with every credential header held aside as ``***``."""
        headers = raw_params.get("headers")
        if not isinstance(headers, Mapping):
            return super().bind_params(raw_params)
        held = {name: value for name, value in headers.items() if isinstance(value, Credential)}
        if held:
            masked = {name: str(value) for name, value in held.items()}
            raw_params = {**raw_params, "headers": {**headers, **masked}}
        params = super().bind_params(raw_params)
        params._credentials = held
        return params

    async def execute(
        self, params: HttpRequestParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[HttpBodyOutput]:
        timeout = params.timeout_or(context.config.default_timeout_s)
        payload: dict[str, object] = (
            {"content": params.body.encode()}
            if isinstance(params.body, str)
            else {"json": params.body}
        )
        resp = await http_client.request(
            params.method,
            params.url,
            headers=params.wire_headers(context.config.credential_release),
            params=params.query_params or None,
            timeout=timeout,
            # A redirect would carry the credential to an origin nobody checked.
            follow_redirects=not params._credentials,
            secret_headers=frozenset(params._credentials),
            **payload,  # type: ignore[arg-type]
        )
        resp_body = http_client.body_of(resp)

        return StepOutput(
            value=HttpBodyOutput(resp_body),
            request=HttpRequest(
                method=params.method,
                url=str(resp.url),
                headers=params.headers,
                body=params.body,
            ),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=http_client.headers_of(resp),
                body=resp_body,
            ),
        )

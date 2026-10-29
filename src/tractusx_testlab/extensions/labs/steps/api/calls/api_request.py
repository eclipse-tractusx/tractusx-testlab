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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""``labs/http/api_request`` — call one operation of an API file. **Experimental.**"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.extensions.labs.steps.api.calls.call_contract import (
    MAX_RESPONSE_BYTES,
    ApiCallParams,
    ApiResponseOutput,
    answered,
    find_operation,
    prepared_for,
    records,
    require_expected,
)
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.openapi.operations import ApiRequestError, default_server_url
from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class ApiRequestParams(ApiCallParams):
    """Input contract of ``labs/http/api_request``."""

    base_url: str | None = Field(
        default=None,
        description=(
            "URL the operation's path is appended to, e.g. 'https://sut.example.com/api'. "
            "Omitted, the document's first server URL (absolute http(s) only, its "
            "variables at their defaults)."
        ),
    )


@step("labs/http/api_request")
class ApiRequestStep(BaseStep[ApiRequestParams, ApiResponseOutput]):
    """Call one operation of an API file directly, and return its answer.

    The step builds the request from the document: the method and path of the
    operation, its placeholders filled from ``path_params`` and
    percent-encoded, the query and headers given, ``Accept`` from the
    documented answers. A required parameter or body that is missing, or a
    header value carrying CR or LF, fails the step before anything is sent.
    The request goes to ``base_url`` and nowhere else: redirects are not
    followed, and answers over 10 MiB are refused rather than read.

    Put ``labs/validate/api_response`` under ``validate:`` to check the answer
    against what the operation documents.
    """

    params_model = ApiRequestParams
    output_model = ApiResponseOutput

    async def execute(
        self, params: ApiRequestParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ApiResponseOutput]:
        document = params.api
        operation = find_operation(document, params.operation)
        base_url = params.base_url or default_server_url(document)
        if not base_url:
            raise ApiRequestError(
                operation.label,
                ["no base_url was given and the document's first server is not an absolute URL"],
            )
        prepared = prepared_for(params, operation, base_url)
        response = await http_client.request(
            prepared.method,
            prepared.url,
            headers=prepared.headers,
            timeout=params.timeout_or(context.config.default_timeout_s),
            follow_redirects=False,
            max_response_bytes=MAX_RESPONSE_BYTES,
            **prepared.payload,
        )
        output = answered(context, definition, document, operation, response, params.expect)
        require_expected(output, params.expect, operation.label)
        request, answer = records(
            prepared, str(response.url), prepared.headers, params.body, output
        )
        return StepOutput(value=output, request=request, response=answer)

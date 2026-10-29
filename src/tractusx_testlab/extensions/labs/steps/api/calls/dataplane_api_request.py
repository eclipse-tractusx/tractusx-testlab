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

"""``labs/connector/dataplane/api_request`` — call an API file's operation through a data plane. **Experimental.**"""

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
    records,
    require_expected,
)
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.openapi.operations import ApiRequestError, prepare, server_base_path
from tractusx_testlab.steps.connector.dataplane_access import DataplaneAddressParams, call_dataplane
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import DATAPLANE_URL

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

#: Stands in for the data plane while the request is built; replaced before sending.
_PLACEHOLDER_BASE = "http://dataplane.invalid"


class DataplaneApiRequestParams(ApiCallParams, DataplaneAddressParams):
    """Input contract of ``labs/connector/dataplane/api_request``."""

    base_path: str | None = Field(
        default=None,
        description=(
            "Prefix stripped from the operation's path before it is appended to the data-plane "
            "URL, for a document whose paths repeat the asset's base URL. Omitted, the path "
            "part of the document's first server URL."
        ),
    )


@step("labs/connector/dataplane/api_request")
class DataplaneApiRequestStep(BaseStep[DataplaneApiRequestParams, ApiResponseOutput]):
    """Call one operation of an API file through a data plane, and return its answer.

    The request is built from the document as ``labs/http/api_request`` builds
    it, and sent as ``connector/dataplane/http_request`` sends: to the
    ``dataplane_url`` and with the ``edr_token`` an earlier step published
    (``pull_data_filtered``, ``initiate_transfer``, ``get_edr``), unless given;
    ``edr_token: ''`` sends none. Redirects are not followed.

    Under ``validate:``, ``labs/validate/api_response`` with ``data_plane: true``
    tells a data plane's own refusal (401/403) or failure to reach the API
    (502/504) apart from an answer of the API.
    """

    params_model = DataplaneApiRequestParams
    output_model = ApiResponseOutput

    async def execute(
        self,
        params: DataplaneApiRequestParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[ApiResponseOutput]:
        document = params.api
        operation = find_operation(document, params.operation)
        endpoint = params.resolved_endpoint(context.get_str(DATAPLANE_URL)).rstrip("/")
        if not endpoint:
            raise ApiRequestError(
                operation.label,
                ["no dataplane_url was given and no earlier step published one"],
            )
        prepared = prepare(
            operation,
            base_url=_PLACEHOLDER_BASE,
            path_params=params.path_params,
            query=params.query,
            headers=params.headers,
            body=params.body,
            content_type=params.content_type,
            accept=params.accept,
        )
        base_path = (
            server_base_path(document) if params.base_path is None else params.base_path
        ).rstrip("/")
        path = prepared.target
        if base_path and (path.startswith((base_path + "/", base_path + "?")) or path == base_path):
            path = path[len(base_path) :]
        exchange = await call_dataplane(
            context,
            params,
            endpoint + path,
            method=prepared.method,
            headers=prepared.headers,
            timeout=params.timeout_or(context.config.default_timeout_s),
            follow_redirects=False,
            max_response_bytes=MAX_RESPONSE_BYTES,
            **prepared.payload,
        )
        output = answered(
            context, definition, document, operation, exchange.response, params.expect
        )
        require_expected(output, params.expect, operation.label)
        request, answer = records(
            prepared, str(exchange.response.url), exchange.recorded_headers, params.body, output
        )
        return StepOutput(value=output, request=request, response=answer)

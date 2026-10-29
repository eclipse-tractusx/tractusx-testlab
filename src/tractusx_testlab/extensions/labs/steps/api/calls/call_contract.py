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

"""What every step that calls an operation of an API file takes and returns. **Experimental.**

The API is the document a test names (``${{ env.apis.<id> }}``, ADR-0030) and
the operation is named in it — by ``operationId`` or as ``METHOD /path``. The
answer comes back with the operation it answered, so
``labs/validate/api_response`` can check it without being told again.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import Field, field_validator

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.models.primitives.exceptions import ExecutionError
from tractusx_testlab.openapi import BoundApiDocument
from tractusx_testlab.openapi.conformance import expect_matches
from tractusx_testlab.openapi.operations import (
    ApiRequestError,
    Operation,
    PreparedRequest,
    is_json_media,
    operation_index,
    prepare,
)
from tractusx_testlab.steps.shared_models import HttpTransportParams
from tractusx_testlab.steps.step_contract import StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

#: The largest answer an API call step reads: 10 MiB, decoded. A larger one
#: fails the step instead of being held, checked or recorded.
MAX_RESPONSE_BYTES = 10 * 1024 * 1024

_EXPECT_WORDS = frozenset({"success", "error", "1XX", "2XX", "3XX", "4XX", "5XX"})


def check_expect(value: Any) -> Any:
    """``expect`` is a status (100-599), a status class (``4XX``), ``success`` or ``error``."""
    if value is None or (
        isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599
    ):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit() and 100 <= int(text) <= 599:
            return int(text)
        if text.upper() in _EXPECT_WORDS or text.lower() in _EXPECT_WORDS:
            return text.upper() if "X" in text.upper() else text.lower()
    raise ValueError(
        "expect must be a status (100-599), a class such as '4XX', 'success' or 'error'"
    )


def check_api(value: Any) -> Any:
    """``api`` is an API file of the TCK, as ``${{ env.apis.<id> }}`` resolves it."""
    if isinstance(value, BoundApiDocument):
        return value
    raise ValueError(
        "api must be an API file of the TCK, written '${{ env.apis.<id> }}'"
        + (f"; got the text {value[:80]!r}" if isinstance(value, str) else "")
    )


class ApiDocumentParams(StepParams):
    """An API file of the TCK."""

    api: Any = Field(
        description=(
            "The API file, written '${{ env.apis.<id> }}'. Recorded by its id and digest, "
            "never as the document."
        ),
    )

    @field_validator("api")
    @classmethod
    def _is_an_api_file(cls, value: Any) -> Any:
        return check_api(value)


class ApiOperationParams(ApiDocumentParams):
    """The API and one operation in it."""

    operation: str = Field(
        min_length=1,
        description="The operation: its operationId, or 'METHOD /path' exactly as the document writes the path.",
    )


class ApiCallParams(ApiOperationParams, HttpTransportParams):
    """Input contract shared by the steps that call one operation of an API file."""

    path_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Values of the path's placeholders, by name; each is percent-encoded as one segment.",
    )
    query: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Query parameters, by name; a list repeats the parameter. Plugs in the 'query' "
            "that 'security/api_key' returns."
        ),
    )
    body: Any = Field(
        default=None, description="Request body; an object or list is sent as JSON, text as it is."
    )
    content_type: str | None = Field(
        default=None,
        description="Content-Type of the body; omitted, the operation's first documented one (JSON if documented).",
    )
    accept: str | None = Field(
        default=None,
        description="Accept header; omitted, the media types the operation documents for its 2XX answers.",
    )
    expect: int | str | None = Field(
        default=None,
        description=(
            "The answer the test expects: a status (404), a class ('4XX'), 'success' (2XX) or "
            "'error' (400 and up). Another answer fails the step. A request expected to be "
            "refused with a 4xx counts as sent wrong on purpose for 'labs/validate/api_errors'."
        ),
    )

    @field_validator("expect", mode="before")
    @classmethod
    def _is_an_expectation(cls, value: Any) -> Any:
        return check_expect(value)


class ApiOperationRef(StepPayload):
    """The operation an answer belongs to."""

    api: str = Field(description="Id of the API file, as declared in env.apis.")
    id: str | None = Field(default=None, description="operationId, when the document gives one.")
    method: str = Field(description="HTTP method.")
    path: str = Field(description="Path template, as the document writes it.")


class ApiResponseOutput(StepPayload):
    """Output contract of the API call steps: the answer and the operation it answers."""

    status_code: int = Field(description="Status the API answered with.")
    response_body: Any = Field(
        default=None, description="Body: parsed JSON for a JSON media type, else text."
    )
    response_headers: dict[str, str] = Field(
        default_factory=dict, description="Response headers, with the casing the server sent."
    )
    operation: ApiOperationRef = Field(description="The operation called.")


class UnexpectedStatusError(ExecutionError):
    """The API answered, with a status the test did not expect."""

    code = "API_STATUS_UNEXPECTED"


def find_operation(document: BoundApiDocument, name: str) -> Operation:
    """The operation *name* means in *document*, or a refusal naming the closest ones."""
    index = operation_index(document)
    found = index.find(name)
    if found is not None:
        return found
    hints = index.suggestions(name)
    hint = f"; did you mean {', '.join(repr(h) for h in hints)}?" if hints else ""
    raise ApiRequestError(name, [f"API '{document.api_id}' has no operation '{name}'{hint}"])


def prepared_for(params: ApiCallParams, operation: Operation, base_url: str) -> PreparedRequest:
    """The request *params* ask for, against *base_url*."""
    return prepare(
        operation,
        base_url=base_url,
        path_params=params.path_params,
        query=params.query,
        headers=params.headers,
        body=params.body,
        content_type=params.content_type,
        accept=params.accept,
    )


def parsed_body(response: httpx.Response) -> Any:
    """The body as JSON for any JSON media type (``+json`` too), else as text."""
    if not response.content:
        return None
    if is_json_media(response.headers.get("content-type", "")):
        try:
            return response.json()
        except ValueError:
            return response.text
    return response.text


def answered(
    context: StepContext,
    definition: StepDefinition,
    document: BoundApiDocument,
    operation: Operation,
    response: httpx.Response,
    expect: int | str | None,
) -> ApiResponseOutput:
    """The output for *response*, noted for ``labs/validate/api_errors``."""
    headers = {
        name.decode("latin-1"): value.decode("latin-1") for name, value in response.headers.raw
    }
    body = parsed_body(response)
    context.steps.api_exchanges.note(
        step=definition.id,
        api=document.api_id,
        operation=operation.label,
        status=response.status_code,
        headers=headers,
        body=body,
        expect=expect,
    )
    return ApiResponseOutput(
        status_code=response.status_code,
        response_body=body,
        response_headers=headers,
        operation=ApiOperationRef(
            api=document.api_id,
            id=operation.operation_id,
            method=operation.method,
            path=operation.path,
        ),
    )


def require_expected(output: ApiResponseOutput, expect: int | str | None, label: str) -> None:
    """Fail the step when the answer is not the one the test expected."""
    if expect_matches(output.status_code, expect):
        return
    error = UnexpectedStatusError(f"{label} answered {output.status_code}, expected {expect}.")
    error.diagnostics = {"operation": label, "status": output.status_code, "expect": expect}
    raise error


def records(
    prepared: PreparedRequest,
    url: str,
    request_headers: Mapping[str, str],
    body: Any,
    output: ApiResponseOutput,
) -> tuple[HttpRequest, HttpResponse]:
    """The step's request and response records: a summary, never the document."""
    return (
        HttpRequest(method=prepared.method, url=url, headers=dict(request_headers), body=body),
        HttpResponse(
            status_code=output.status_code,
            headers=output.response_headers,
            body=output.response_body,
        ),
    )

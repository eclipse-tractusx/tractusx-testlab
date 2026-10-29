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

"""``labs/validate/api_response`` — an answer is one its operation documents. **Experimental.**

Usable two ways. Under ``validate:`` of an API call step it reads the step's
own answer — no ``input`` needed — and finds the document by the API id the
answer carries::

    - uses: labs/http/api_request
      with: { api: "${{ env.apis.ich }}", operation: check_health_health_get }
      validate:
        - uses: labs/validate/api_response

As a step it checks the answer the last API call step published, or the one
given as ``input``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.extensions.labs.steps.api.calls.call_contract import (
    check_api,
    check_expect,
    find_operation,
)
from tractusx_testlab.extensions.labs.steps.api.verdicts.verdict_report import nested, summary
from tractusx_testlab.models import StepDefinition, TestLabError
from tractusx_testlab.openapi import BoundApiDocument, recorded
from tractusx_testlab.openapi.conformance import CHECKS, ResponseVerdict, check_response
from tractusx_testlab.steps.assertions import (
    CheckOutcome,
    RegisteredValidation,
    register_validation,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

USES = "labs/validate/api_response"

#: The outputs of an API call step, read as the answer when no ``input`` is given.
ANSWER_FIELDS = ("status_code", "response_body", "response_headers", "operation")


class UncheckableAnswerError(TestLabError):
    """The answer, the document or the operation to check it against is missing."""

    code = "API_RESPONSE_UNCHECKABLE"
    origin = "authoring"


def verdict_of(
    answer: Any,
    *,
    api: Any = None,
    operation: str | None = None,
    expect: Any = None,
    data_plane: bool = False,
    variables: Callable[[str], object] | None = None,
) -> ResponseVerdict:
    """Check *answer* (``status_code``, ``response_body``, ``response_headers``, ``operation``).

    Raises:
        UncheckableAnswerError: nothing says which document or operation, or
            *answer* is not an answer.
    """
    if not isinstance(answer, Mapping) or not isinstance(answer.get("status_code"), int):
        raise UncheckableAnswerError(
            "The input is not an API answer: it needs 'status_code', 'response_body' and "
            "'response_headers', as labs/http/api_request returns them."
        )
    named = answer.get("operation")
    ref: Mapping[str, Any] = named if isinstance(named, Mapping) else {}
    document = api if api is not None else _bound(ref.get("api"), variables)
    if not isinstance(document, BoundApiDocument):
        raise UncheckableAnswerError(
            "No API file to check the answer against: give 'api: ${{ env.apis.<id> }}', or "
            "check the answer of a labs API call step."
        )
    name = (
        operation
        or ref.get("id")
        or (f"{ref.get('method')} {ref.get('path')}" if ref.get("path") else None)
    )
    if not name:
        raise UncheckableAnswerError("No operation to check the answer against: give 'operation'.")
    headers = answer.get("response_headers")
    return check_response(
        document,
        find_operation(document, str(name)),
        status=answer["status_code"],
        headers=headers if isinstance(headers, Mapping) else {},
        body=answer.get("response_body"),
        expect=check_expect(expect),
        data_plane=data_plane,
    )


def _bound(api_id: Any, variables: Callable[[str], object] | None) -> object:
    if not isinstance(api_id, str) or variables is None:
        return None
    return variables(f"apis.{api_id}")


def _as_validation(subject: object, params: dict, variables: Any) -> CheckOutcome:
    try:
        verdict = verdict_of(
            subject,
            api=params.get("api"),
            operation=params.get("operation"),
            expect=params.get("expect"),
            data_plane=bool(params.get("data_plane", False)),
            variables=variables,
        )
    except (TestLabError, ValueError) as exc:
        return CheckOutcome(False, str(exc), expected=recorded(params))
    return CheckOutcome(
        verdict.passed,
        summary(verdict.problems),
        expected=recorded(params),
        actual=[problem.as_dict() for problem in verdict.problems] or None,
    )


register_validation(
    RegisteredValidation(
        USES,
        _as_validation,
        input_optional=True,
        checks=(
            "**Experimental (labs).** Check an API answer against what its operation documents: "
            "status, `expect`, Content-Type, body schema, required headers. Without `input`, the "
            "answer of the API call step it is under."
        ),
        reads="`input`, `api`, `operation`, `expect`, `data_plane`, `severity`",
    )
)


class ApiResponseCheckParams(StepParams):
    """Input contract of ``labs/validate/api_response`` as a step."""

    input: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The answer to check, as an API call step returns it; omitted, the one the "
            "last API call step published."
        ),
    )
    api: Any = Field(
        default=None, description="API file, '${{ env.apis.<id> }}'; omitted, the answer's own."
    )
    operation: str | None = Field(default=None, description="Operation; omitted, the answer's own.")
    expect: int | str | None = Field(
        default=None, description="Expected status, class ('4XX'), 'success' or 'error'."
    )
    data_plane: bool = Field(
        default=False,
        description=(
            "The answer came through a data plane: a 401/403 (EDR refused) or 502/504 (API "
            "unreachable) is reported as the data plane's, not checked against the document."
        ),
    )

    @field_validator("api")
    @classmethod
    def _is_an_api_file(cls, value: Any) -> Any:
        return value if value is None else check_api(value)

    @field_validator("expect", mode="before")
    @classmethod
    def _is_an_expectation(cls, value: Any) -> Any:
        return check_expect(value)


class ApiResponseVerdict(StepPayload):
    """Output contract of ``labs/validate/api_response``."""

    passed: bool = Field(description="Whether every check held.")
    status_code: int = Field(description="Status of the answer checked.")
    operation: str = Field(description="The operation it was checked against.")
    problems: list[dict[str, str]] = Field(
        default_factory=list,
        description="Each problem: check, message, and for a body the pointer, keyword, schema_location, received.",
    )


@step("labs/validate/api_response")
class ApiResponseCheckStep(BaseStep[ApiResponseCheckParams, ApiResponseVerdict]):
    """Check an answer against what its operation documents in the API file.

    In order: the status is documented (exactly, as ``4XX`` or as
    ``default``); it is the ``expect``-ed one, if given; the Content-Type is a
    documented media type for it; the body validates against that schema
    (OpenAPI 3.0 schemas read with their 3.0 meaning — ``nullable``, boolean
    ``exclusiveMinimum``); every required response header is there. Every
    problem is reported with where it is in the body, the schema keyword and
    where that keyword is in the document. The step fails when any check does,
    and keeps the verdict as its output.
    """

    params_model = ApiResponseCheckParams
    output_model = ApiResponseVerdict

    async def execute(
        self, params: ApiResponseCheckParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ApiResponseVerdict]:
        answer = params.input or {name: context.get_variable(name) for name in ANSWER_FIELDS}
        verdict = verdict_of(
            answer,
            api=params.api,
            operation=params.operation,
            expect=params.expect,
            data_plane=params.data_plane,
            variables=context.get_variable,
        )
        output = ApiResponseVerdict(
            passed=verdict.passed,
            status_code=verdict.status,
            operation=verdict.operation,
            problems=[problem.as_dict() for problem in verdict.problems],
        )
        checks = [
            (name, verdict.problems_of(name))
            for name in (*CHECKS, "data_plane")
            if name in verdict.checked
        ]
        return StepOutput(value=output, nested=nested(USES, checks))

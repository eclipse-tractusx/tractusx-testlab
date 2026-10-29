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

"""``labs/validate/api_errors`` — a test's error answers, judged together. **Experimental.**"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, field_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.extensions.labs.steps.api.calls.call_contract import (
    check_expect,
    find_operation,
)
from tractusx_testlab.extensions.labs.steps.api.verdicts.verdict_report import nested
from tractusx_testlab.models import StepDefinition, TestLabError
from tractusx_testlab.openapi import BoundApiDocument
from tractusx_testlab.openapi.conformance import ErrorAnswer, error_problems
from tractusx_testlab.openapi.exchanges import ApiExchange
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

USES = "labs/validate/api_errors"

#: The three checks, in the order they are reported.
ERROR_CHECKS = ("format", "leaks", "client_errors")


class ApiErrorsParams(StepParams):
    """Input contract of ``labs/validate/api_errors``."""

    responses: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Answers to judge, each as an API call step returns it (status_code, "
            "response_body, response_headers, operation) plus an optional 'expect'; omitted, "
            "every answer the test's labs API call steps received so far."
        ),
    )
    steps: list[str] | None = Field(
        default=None,
        description=(
            "Only the answers of these steps (their ids) of the test; omitted, every labs API "
            "call step's. Ignored when 'responses' is given."
        ),
    )
    format: Literal["declared", "problem+json"] = Field(
        default="declared",
        description=(
            "'declared': each error body matches the schema its operation documents for its "
            "status; 'problem+json': each is RFC 9457 problem details. Ignored when 'schema' is given."
        ),
    )
    json_schema: dict[str, Any] | None = Field(
        default=None,
        validation_alias="schema",
        serialization_alias="schema",
        description="One JSON Schema every error body must match, e.g. '${{ env.schemas.error }}'.",
    )
    leaks: bool = Field(
        default=True,
        description="Look for stack traces, exception names, SQL, file paths and internal addresses in error bodies.",
    )

    @field_validator("responses")
    @classmethod
    def _expectations(cls, value: Any) -> Any:
        for entry in value or []:
            check_expect(entry.get("expect"))
        return value


class ApiErrorsVerdict(StepPayload):
    """Output contract of ``labs/validate/api_errors``."""

    passed: bool = Field(description="Whether every check held for every error answer.")
    checked: int = Field(description="Answers looked at.")
    errors: int = Field(description="Of those, error answers (status 400 and up).")
    problems: list[dict[str, Any]] = Field(
        default_factory=list, description="Each problem: check, operation, status, message."
    )


@step("labs/validate/api_errors")
class ApiErrorsStep(BaseStep[ApiErrorsParams, ApiErrorsVerdict]):
    """Judge the error answers of a test's API calls together.

    Three checks over every answer with status 400 or more — those the test's
    ``labs/http/api_request``, ``labs/connector/dataplane/api_request`` and
    ``labs/http/api_sweep`` steps received, or the ``responses`` given:

    * **format** — every error body has the one error format: ``schema``, RFC
      9457 problem details (``format: problem+json``), or the schema its
      operation documents for its status (the default);
    * **leaks** — no body gives away a stack trace, an exception class, SQL,
      a file path, a private address or an internal host name;
    * **client_errors** — no request the test sent wrong on purpose
      (``expect`` 4xx, ``4XX`` or ``error``) was answered with a 5xx.

    The step fails when a check does, and keeps every problem as its output.
    """

    params_model = ApiErrorsParams
    output_model = ApiErrorsVerdict

    async def execute(
        self, params: ApiErrorsParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ApiErrorsVerdict]:
        if params.responses is None:
            answers = [
                _from_exchange(e, context.get_variable)
                for e in context.steps.api_exchanges.entries()
                if params.steps is None or e.step in params.steps
            ]
        else:
            answers = [_from_given(entry, context.get_variable) for entry in params.responses]
        found = error_problems(
            answers, error_format=params.format, schema=params.json_schema, check_leaks=params.leaks
        )
        problems = [
            {
                "check": problem.check,
                "operation": answer.label,
                "status": answer.status,
                **problem.as_dict(),
            }
            for answer, problem in found
        ]
        output = ApiErrorsVerdict(
            passed=not found,
            checked=len(answers),
            errors=sum(answer.is_error for answer in answers),
            problems=problems,
        )
        checks = [
            (name, [problem for _, problem in found if problem.check == name])
            for name in ERROR_CHECKS
            if name != "leaks" or params.leaks
        ]
        return StepOutput(value=output, nested=nested(USES, checks))


def _from_exchange(exchange: ApiExchange, variables: Callable[[str], object]) -> ErrorAnswer:
    document = variables(f"apis.{exchange.api}")
    return _answer(
        document,
        exchange.operation,
        exchange.status,
        exchange.headers,
        exchange.body,
        exchange.expect,
    )


def _from_given(entry: Mapping[str, Any], variables: Callable[[str], object]) -> ErrorAnswer:
    status = entry.get("status_code")
    if not isinstance(status, int):
        raise ValueError("each entry of 'responses' needs an integer 'status_code'")
    named = entry.get("operation")
    ref: Mapping[str, Any] = named if isinstance(named, Mapping) else {}
    document = variables(f"apis.{ref.get('api')}") if ref.get("api") else None
    name = ref.get("id") or (f"{ref.get('method')} {ref.get('path')}" if ref.get("path") else "")
    headers = entry.get("response_headers")
    return _answer(
        document,
        str(name),
        status,
        headers if isinstance(headers, Mapping) else {},
        entry.get("response_body"),
        check_expect(entry.get("expect")),
    )


def _answer(
    document: object, name: str, status: int, headers: Mapping[str, str], body: Any, expect: Any
) -> ErrorAnswer:
    operation = None
    if isinstance(document, BoundApiDocument) and name:
        try:
            operation = find_operation(document, name)
        except TestLabError:
            operation = None
    return ErrorAnswer(
        label=name or "an answer",
        status=status,
        headers=headers,
        body=body,
        expect=expect,
        document=document if isinstance(document, BoundApiDocument) else None,
        operation=operation,
    )

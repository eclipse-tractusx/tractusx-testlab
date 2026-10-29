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

"""Whether the error answers of an API are consistent, discreet and fair.

Three checks over every error answer (status 400 and up) a test collected:

* **format** — each body has the one error format: the schema the test gives,
  RFC 9457 problem details (``format: problem+json``: the media type
  ``application/problem+json``, the members typed as the RFC says, ``status``
  equal to the HTTP status), or by default the schema its operation documents
  for that status;
* **leaks** — no body gives away the server behind it
  (:mod:`.leak_patterns`);
* **client_errors** — a request the test sent wrong on purpose (``expect`` of
  a 4xx status, ``4XX`` or ``error``) is not answered with a 5xx: a server that
  fails on bad input has a bug, not a validation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import jsonschema

from tractusx_testlab.logging.masking import mask
from tractusx_testlab.openapi.conformance.leak_patterns import leaks_in
from tractusx_testlab.openapi.conformance.response_conformance import (
    Problem,
    check_response,
)
from tractusx_testlab.openapi.operations.operation_index import Operation

#: RFC 9457 §3.1: the members a problem details object may carry, typed.
PROBLEM_DETAILS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "integer", "minimum": 100, "maximum": 599},
        "detail": {"type": "string"},
        "instance": {"type": "string"},
    },
}
PROBLEM_JSON = "application/problem+json"

#: The formats ``labs/validate/api_errors`` checks against.
FORMATS = ("declared", "problem+json")


@dataclass(frozen=True, slots=True)
class ErrorAnswer:
    """One answer to check: what was called, what came back, what was expected."""

    label: str
    status: int
    headers: Mapping[str, str]
    body: Any
    expect: int | str | None = None
    #: The API document and operation, when known — needed by ``format: declared``.
    document: Mapping[str, Any] | None = None
    operation: Operation | None = None

    @property
    def is_error(self) -> bool:
        return self.status >= 400

    @property
    def was_sent_wrong(self) -> bool:
        """Whether the test meant the request to be refused as the client's fault."""
        expect = self.expect
        if isinstance(expect, int):
            return 400 <= expect < 500
        return str(expect).strip().upper() in {"4XX", "ERROR"} or str(expect).startswith("4")


def error_problems(
    answers: list[ErrorAnswer],
    *,
    error_format: str = "declared",
    schema: Mapping[str, Any] | None = None,
    check_leaks: bool = True,
) -> list[tuple[ErrorAnswer, Problem]]:
    """Every problem of every error answer in *answers*, in order."""
    validator = None
    if schema is not None:
        validator = jsonschema.validators.validator_for(schema)(schema)
    elif error_format == "problem+json":
        validator = jsonschema.Draft202012Validator(PROBLEM_DETAILS_SCHEMA)
    found: list[tuple[ErrorAnswer, Problem]] = []
    for answer in answers:
        if answer.was_sent_wrong and answer.status >= 500:
            found.append(
                (
                    answer,
                    Problem(
                        "client_errors",
                        f"a request sent wrong on purpose (expect {answer.expect}) was answered {answer.status}; a client error is a 4xx",
                    ),
                )
            )
        if not answer.is_error:
            continue
        found += [
            (answer, problem) for problem in _format_problems(answer, error_format, validator)
        ]
        if check_leaks:
            found += [
                (
                    answer,
                    Problem(
                        "leaks",
                        f"the body gives away a {leak.kind.replace('_', ' ')}",
                        received=str(mask(leak.excerpt)),
                    ),
                )
                for leak in leaks_in(_text(answer.body))
            ]
    return found


def _format_problems(answer: ErrorAnswer, error_format: str, validator: Any) -> list[Problem]:
    if validator is None:
        if answer.document is None or answer.operation is None:
            return [
                Problem(
                    "format",
                    "the operation is not known, so its declared error format cannot be checked; give 'schema' or 'format'",
                )
            ]
        verdict = check_response(
            answer.document,
            answer.operation,
            status=answer.status,
            headers=answer.headers,
            body=answer.body,
        )
        return [
            Problem(
                "format",
                f"{problem.check}: {problem.message}",
                problem.pointer,
                problem.keyword,
                problem.schema_location,
                problem.received,
            )
            for problem in verdict.problems
        ]
    problems: list[Problem] = []
    content_type = next(
        (str(v) for k, v in answer.headers.items() if k.lower() == "content-type"), ""
    )
    if error_format == "problem+json" and not content_type.lower().startswith(PROBLEM_JSON):
        problems.append(
            Problem("format", f"Content-Type is '{content_type or 'missing'}', not {PROBLEM_JSON}")
        )
    body = _parsed(answer.body)
    if body is None:
        return [*problems, Problem("format", "the body is not JSON")]
    for error in validator.iter_errors(body):
        pointer = "".join(f"/{token}" for token in error.absolute_path)
        problems.append(
            Problem(
                "format",
                str(mask(error.message))[:400],
                pointer=pointer,
                keyword=str(error.validator),
            )
        )
    if (
        error_format == "problem+json"
        and isinstance(body, dict)
        and isinstance(body.get("status"), int)
        and body["status"] != answer.status
    ):
        problems.append(
            Problem(
                "format",
                f"member 'status' is {body['status']}, the answer's status is {answer.status}",
            )
        )
    return problems


def _parsed(body: Any) -> Any:
    if isinstance(body, str):
        try:
            return json.loads(body)
        except ValueError:
            return None
    return body


def _text(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    try:
        return json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(body)

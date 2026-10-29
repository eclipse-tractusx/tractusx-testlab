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

"""Whether an answer is one the operation documents.

In order, each check reported on its own so a reader sees which held:

1. **status** — the status is documented: exactly (``404``), by range
   (``4XX``) or by ``default``, in that order of preference;
2. **expect** — it is the one the test expected, when it said;
3. **content_type** — the ``Content-Type`` is a media type documented for that
   status (``application/*`` and ``*/*`` match as wildcards), and a body
   arrives exactly when one is documented;
4. **body** — the body validates against that status and media type's schema;
5. **headers** — every response header the status declares ``required`` is there.

Every problem is collected; nothing stops at the first. With ``data_plane``, a
401/403 (the data plane refused the EDR) or a 502/504 (the data plane could not
reach the API) is reported as what it is — the API was never asked — instead of
as an undocumented status.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from tractusx_testlab.openapi.conformance.validator_cache import schema_problems
from tractusx_testlab.openapi.operations.operation_index import Operation
from tractusx_testlab.openapi.operations.pointers import PointerError, child, follow
from tractusx_testlab.openapi.operations.request_building import is_json_media

#: The order the checks run and are reported in.
CHECKS = ("status", "expect", "content_type", "body", "headers")

#: What a data plane answers itself, and what it means.
DATA_PLANE_STATUSES = {
    401: "the data plane refused the EDR token (401)",
    403: "the data plane refused the EDR token (403)",
    502: "the data plane could not reach the API behind it (502)",
    504: "the data plane timed out reaching the API behind it (504)",
}


@dataclass(frozen=True, slots=True)
class Problem:
    """One way an answer is not what the operation documents."""

    check: str
    message: str
    pointer: str | None = None
    keyword: str | None = None
    schema_location: str | None = None
    received: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True, slots=True)
class ResponseVerdict:
    """The checks run on one answer, and every problem they found."""

    operation: str
    status: int
    checked: tuple[str, ...] = ()
    problems: tuple[Problem, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.problems

    def problems_of(self, check: str) -> list[Problem]:
        return [problem for problem in self.problems if problem.check == check]


def expect_matches(status: int, expect: int | str | None) -> bool:
    """Whether *status* is what ``expect`` (``200``, ``"4XX"``, ``"success"``, ``"error"``) asks."""
    if expect is None:
        return True
    if isinstance(expect, int):
        return status == expect
    text = str(expect).strip().upper()
    if text == "SUCCESS":
        return 200 <= status < 300
    if text == "ERROR":
        return status >= 400
    if len(text) == 3 and text.endswith("XX") and text[0].isdigit():
        return status // 100 == int(text[0])
    return text.isdigit() and status == int(text)


def documented_response(
    document: Mapping[str, Any], operation: Operation, status: int
) -> tuple[str, Mapping[str, Any], str] | None:
    """The response documented for *status*: its key, its object and where that object is."""
    responses = operation.responses
    for key in (str(status), f"{str(status)[0]}XX", f"{str(status)[0]}xx", "default"):
        if key in responses:
            at = child(operation.location, "responses", key)
            try:
                response, at = follow(document, responses[key], at)
            except PointerError:
                return None
            return (key, response, at) if isinstance(response, Mapping) else None
    return None


def check_response(
    document: Mapping[str, Any],
    operation: Operation,
    *,
    status: int,
    headers: Mapping[str, str],
    body: Any,
    expect: int | str | None = None,
    data_plane: bool = False,
) -> ResponseVerdict:
    """Every check of :data:`CHECKS` on one answer to *operation*."""
    if data_plane and status in DATA_PLANE_STATUSES:
        if expect is not None and expect_matches(status, expect):
            return ResponseVerdict(operation.label, status, ("expect",))
        reason = DATA_PLANE_STATUSES[status]
        message = f"{reason}; the API was never asked, so the answer is not checked against it"
        return ResponseVerdict(
            operation.label, status, ("data_plane",), (Problem("data_plane", message),)
        )
    problems: list[Problem] = []
    found = documented_response(document, operation, status)
    if found is None:
        documented = ", ".join(str(key) for key in operation.responses) or "none"
        problems.append(
            Problem(
                "status",
                f"status {status} is not documented for {operation.key} (documented: {documented})",
            )
        )
    if not expect_matches(status, expect):
        problems.append(Problem("expect", f"status {status} is not the expected {expect}"))
    if found is not None:
        problems += _content_problems(document, operation, found, headers, body)
        problems += _header_problems(document, found, headers)
    return ResponseVerdict(operation.label, status, CHECKS, tuple(problems))


def _content_problems(
    document: Mapping[str, Any],
    operation: Operation,
    found: tuple[str, Mapping[str, Any], str],
    headers: Mapping[str, str],
    body: Any,
) -> list[Problem]:
    key, response, at = found
    content = response.get("content") if isinstance(response.get("content"), Mapping) else {}
    has_body = body not in (None, "", b"") and operation.method != "HEAD"
    received_type = _header(headers, "content-type")
    if not content:
        if has_body:
            return [
                Problem(
                    "content_type",
                    f"status {key} documents no body, but one arrived ({received_type or 'no Content-Type'})",
                )
            ]
        return []
    if not has_body:
        if operation.method == "HEAD" or str(key) == "204":
            return []
        return [
            Problem(
                "content_type",
                f"status {key} documents a body ({', '.join(content)}) and none arrived",
            )
        ]
    if not received_type:
        return [
            Problem(
                "content_type",
                f"a body arrived without a Content-Type; documented: {', '.join(content)}",
            )
        ]
    media = _matching_media(content, received_type)
    if media is None:
        return [
            Problem(
                "content_type",
                f"Content-Type '{received_type}' is not documented for status {key} (documented: {', '.join(content)})",
                received=received_type,
            )
        ]
    entry = content[media]
    if not (isinstance(entry, Mapping) and "schema" in entry) or not is_json_media(received_type):
        return []
    value, problem = _json(body)
    if problem:
        return [Problem("body", problem)]
    schema_at = child(at, "content", media, "schema")
    return [
        Problem(
            "body",
            found_problem.message,
            pointer=found_problem.pointer,
            keyword=found_problem.keyword,
            schema_location=found_problem.schema_location,
            received=found_problem.received,
        )
        for found_problem in schema_problems(document, schema_at, value)
    ]


def _header_problems(
    document: Mapping[str, Any],
    found: tuple[str, Mapping[str, Any], str],
    headers: Mapping[str, str],
) -> list[Problem]:
    key, response, at = found
    declared = response.get("headers")
    problems: list[Problem] = []
    for name, header in declared.items() if isinstance(declared, Mapping) else ():
        if str(name).lower() == "content-type":
            continue  # described by `content`, ignored here by the specification
        try:
            header, _ = follow(document, header, child(at, "headers", name))
        except PointerError:
            continue
        if (
            isinstance(header, Mapping)
            and header.get("required")
            and _header(headers, str(name)) is None
        ):
            problems.append(
                Problem("headers", f"required response header '{name}' of status {key} is missing")
            )
    return problems


def _header(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    return next((str(value) for key, value in headers.items() if key.lower() == wanted), None)


def _matching_media(content: Mapping[str, Any], received: str) -> str | None:
    essence = received.split(";", 1)[0].strip().lower()
    documented = {str(media).split(";", 1)[0].strip().lower(): media for media in content}
    major = essence.split("/", 1)[0]
    for candidate in (essence, f"{major}/*", "*/*"):
        if candidate in documented:
            return str(documented[candidate])
    return None


def _json(body: Any) -> tuple[Any, str]:
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    if not isinstance(body, str):
        return body, ""
    try:
        return json.loads(body), ""
    except json.JSONDecodeError as exc:
        return None, f"the body is not valid JSON ({exc.msg} at character {exc.pos})"

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

"""Turning an operation and a test's values into the request that is sent.

Everything is checked before anything is sent, and every problem is reported at
once: a required parameter the test did not give, a header value that would
split the request (CR, LF or NUL), a path value that would leave its segment.
Path values are percent-encoded segment by segment — ``/`` included, so
``a/../b`` stays one segment — query values are left to the HTTP client, which
encodes them, and the request goes to *base_url* and nowhere else: the
document's own ``servers`` are a default for the base URL, never a second
target.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlencode

from tractusx_testlab.models.primitives.exceptions import AuthoringError
from tractusx_testlab.openapi.operations.operation_index import Operation
from tractusx_testlab.openapi.operations.servers import SPLITTING, check_base_url

#: An HTTP header name (RFC 9110 §5.1, ``token``).
_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


class ApiRequestError(AuthoringError):
    """The request a test asked for cannot be built; nothing was sent."""

    code = "API_REQUEST_INVALID"

    def __init__(self, label: str, problems: list[str]) -> None:
        self.problems = tuple(problems)
        self.diagnostics = {"operation": label, "problems": list(problems)}
        super().__init__(f"Cannot call {label}: " + "; ".join(problems))


@dataclass(frozen=True, slots=True)
class PreparedRequest:
    """A request ready for the HTTP client: method, URL (query included) and what goes with it."""

    method: str
    url: str
    #: The expanded path, relative to the base URL.
    path: str
    #: The path and its encoded query: what follows the base URL.
    target: str = ""
    query: list[tuple[str, str | int | float | bool | None]] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    #: ``json``, ``content`` or ``data`` for the HTTP client, or nothing.
    payload: dict[str, Any] = field(default_factory=dict)


def is_json_media(media_type: str) -> bool:
    """``application/json`` and every ``+json`` type, parameters ignored."""
    essence = media_type.split(";", 1)[0].strip().lower()
    return essence == "application/json" or essence.endswith("+json")


def expand_path(operation: Operation, values: Mapping[str, Any]) -> tuple[str, list[str]]:
    """The operation's path with each placeholder replaced, and what was wrong."""
    problems: list[str] = []
    parts: list[str] = []
    for literal, name in operation.template:
        parts.append(literal)
        if name is None:
            continue
        if name not in values or values[name] is None:
            problems.append(f"path parameter '{name}' is required and was not given")
            continue
        text, problem = _scalar(values[name], f"path parameter '{name}'")
        if problem:
            problems.append(problem)
        elif text in ("", ".", ".."):
            problems.append(f"path parameter '{name}' may not be '{text}'")
        else:
            parts.append(quote(text, safe=""))
    return "".join(parts), problems


def prepare(
    operation: Operation,
    *,
    base_url: str,
    path_params: Mapping[str, Any],
    query: Mapping[str, Any],
    headers: Mapping[str, str],
    body: Any = None,
    content_type: str | None = None,
    accept: str | None = None,
) -> PreparedRequest:
    """The request for *operation*, or every reason it cannot be built.

    Raises:
        ApiRequestError: listing each missing or unsafe value; nothing is sent.
    """
    problems = check_base_url(base_url)
    path, path_problems = expand_path(operation, path_params)
    problems += path_problems
    problems += [
        f"path parameter '{name}' is not in '{operation.path}'"
        for name in path_params
        if name not in {placeholder for _, placeholder in operation.template if placeholder}
    ]
    pairs, query_problems = _query(operation, query)
    sent_headers, header_problems = _headers(operation, headers, body, content_type, accept)
    problems += query_problems + header_problems
    if body is None and operation.body_required:
        problems.append("the operation requires a request body and none was given")
    if problems:
        raise ApiRequestError(operation.label, problems)
    target = path + (f"?{urlencode(pairs, quote_via=quote)}" if pairs else "")
    return PreparedRequest(
        method=operation.method,
        url=base_url.rstrip("/") + target,
        path=path,
        target=target,
        query=pairs,
        headers=sent_headers,
        payload=_payload(body, sent_headers.get("Content-Type", "")),
    )


def _query(
    operation: Operation, query: Mapping[str, Any]
) -> tuple[list[tuple[str, str | int | float | bool | None]], list[str]]:
    problems = [
        f"query parameter '{p.name}' is required and was not given"
        for p in operation.parameters_in("query")
        if p.required and query.get(p.name) is None
    ]
    pairs: list[tuple[str, str | int | float | bool | None]] = []
    for name, value in query.items():
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item is None:
                continue
            text, problem = _scalar(item, f"query parameter '{name}'")
            if problem or SPLITTING.search(str(name)):
                problems.append(problem or f"query parameter name '{name}' has a control character")
            else:
                pairs.append((str(name), text))
    return pairs, problems


def _headers(
    operation: Operation,
    headers: Mapping[str, str],
    body: Any,
    content_type: str | None,
    accept: str | None,
) -> tuple[dict[str, str], list[str]]:
    given = {name.lower() for name in headers}
    problems = [
        f"header parameter '{p.name}' is required and was not given"
        for p in operation.parameters_in("header")
        if p.required and p.name.lower() not in given
    ]
    problems += [
        f"cookie parameter '{p.name}' is required; send it in a 'Cookie' header"
        for p in operation.parameters_in("cookie")
        if p.required and "cookie" not in given
    ]
    sent = dict(headers)
    if accept is not None:
        sent["Accept"] = accept
    elif "accept" not in given and (documented := _success_media_types(operation)):
        sent["Accept"] = ", ".join(documented)
    if body is not None and "content-type" not in given:
        sent["Content-Type"] = content_type or _request_media_type(operation)
    for name, value in sent.items():
        if not _HEADER_NAME.match(str(name)):
            problems.append(f"header name '{name}' is not a valid HTTP header name")
        elif not isinstance(value, str) or SPLITTING.search(value):
            # Never quote the value: it may be a credential.
            problems.append(f"header '{name}' has a value with CR, LF or NUL, or is not text")
    return sent, problems


def _success_media_types(operation: Operation) -> list[str]:
    types: dict[str, None] = {}
    for status, response in operation.responses.items():
        if str(status).startswith("2") and isinstance(response, Mapping):
            content = response.get("content")
            types.update(dict.fromkeys(content if isinstance(content, Mapping) else ()))
    return list(types)


def _request_media_type(operation: Operation) -> str:
    content = (operation.request_body or {}).get("content")
    types = list(content) if isinstance(content, Mapping) else []
    if "application/json" in types or not types:
        return "application/json"
    return str(types[0])


def _payload(body: Any, media_type: str) -> dict[str, Any]:
    if body is None:
        return {}
    if isinstance(body, str):
        return {"content": body.encode()}
    essence = media_type.split(";", 1)[0].strip().lower()
    if essence == "application/x-www-form-urlencoded" and isinstance(body, Mapping):
        return {"data": {str(k): str(v) for k, v in body.items()}}
    return {"content": json.dumps(body, separators=(",", ":")).encode()}


def _scalar(value: Any, label: str) -> tuple[str, str]:
    """*value* as the text a URL carries, or why it cannot be one."""
    if isinstance(value, bool):
        return ("true" if value else "false"), ""
    if isinstance(value, int | float | str):
        text = str(value)
        if SPLITTING.search(text):
            return "", f"{label} contains CR, LF or NUL"
        return text, ""
    if isinstance(value, list):
        texts = [_scalar(item, label) for item in value]
        problem = next((p for _, p in texts if p), "")
        return ",".join(t for t, _ in texts), problem
    return "", f"{label} must be a string, a number, a boolean or a list of them"

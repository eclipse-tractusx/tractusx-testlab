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

"""The operations of an API document, indexed once per document.

A step names an operation by its ``operationId`` or as ``METHOD /path``
(``GET /v1/parts/{id}``). Both lookups, the parameters merged from the path
item and the operation, and the path template split into literal and
placeholder segments are worked out the first time a document is asked for
them and kept, so a sweep over fifty operations, or a test calling the same one
fifty times, does not walk the document again.

The cache is keyed by the document's digest when it has one (a document bound
to ``env.apis``) and by its identity otherwise, holds a reference to the
document so an identity cannot be reused while cached, and is bounded like the
document cache it sits behind.
"""

from __future__ import annotations

import difflib
import re
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from tractusx_testlab.openapi.operations.pointers import PointerError, child, follow, pointer

#: The HTTP methods a path item may hold an operation under (OpenAPI 3.0/3.1).
METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")

#: Methods that change nothing on the server (RFC 9110 §9.2.1).
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

#: How many indexed documents a process keeps.
CACHE_SIZE = 16

_PLACEHOLDER = re.compile(r"\{([^{}/]+)\}")


@dataclass(frozen=True, slots=True)
class Parameter:
    """One parameter an operation declares, its ``$ref`` already followed."""

    name: str
    location: str  # path | query | header | cookie
    required: bool
    schema: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Operation:
    """One operation of an API document, ready to be called and checked."""

    method: str
    path: str
    operation_id: str | None
    #: Where the operation object is, ``#/paths/~1parts/get``.
    location: str
    parameters: tuple[Parameter, ...] = ()
    #: The request body object, ``$ref`` followed; ``None`` when none is declared.
    request_body: Mapping[str, Any] | None = None
    responses: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    #: The path template as (literal, placeholder) pairs; a trailing literal has ``None``.
    template: tuple[tuple[str, str | None], ...] = ()

    @property
    def key(self) -> str:
        """``GET /parts/{id}`` — the operation however it is named."""
        return f"{self.method} {self.path}"

    @property
    def label(self) -> str:
        """The ``operationId``, else :attr:`key`: what a report calls it."""
        return self.operation_id or self.key

    @property
    def is_write(self) -> bool:
        """Whether calling it may change something on the server."""
        return self.method not in SAFE_METHODS

    @property
    def body_required(self) -> bool:
        return bool(self.request_body and self.request_body.get("required"))

    def parameters_in(self, location: str) -> tuple[Parameter, ...]:
        return tuple(p for p in self.parameters if p.location == location)


@dataclass(frozen=True, slots=True)
class OperationIndex:
    """Every operation of one document, by ``operationId`` and by ``METHOD /path``."""

    operations: tuple[Operation, ...]
    by_id: Mapping[str, Operation]
    by_key: Mapping[str, Operation]

    def find(self, name: str) -> Operation | None:
        """The operation *name* means: an ``operationId``, else ``METHOD /path``."""
        found = self.by_id.get(name)
        if found is not None:
            return found
        method, _, path = name.strip().partition(" ")
        return self.by_key.get(f"{method.upper()} {path.strip()}")

    def suggestions(self, name: str, limit: int = 3) -> list[str]:
        """The names closest to *name*, for a message about one that matched nothing."""
        names = [*self.by_id, *self.by_key]
        return difflib.get_close_matches(name, names, n=limit, cutoff=0.5)

    @property
    def tags(self) -> frozenset[str]:
        return frozenset(tag for operation in self.operations for tag in operation.tags)


_lock = threading.Lock()
_cache: OrderedDict[str, tuple[Mapping[str, Any], OperationIndex]] = OrderedDict()


def document_key(document: Mapping[str, Any]) -> str:
    """What caches derived from *document* are keyed by: its digest, else its identity."""
    digest = getattr(document, "sha256", None)
    return f"sha256:{digest}" if isinstance(digest, str) and digest else f"id:{id(document)}"


def operation_index(document: Mapping[str, Any]) -> OperationIndex:
    """The operations of *document*, indexed on first use and cached."""
    key = document_key(document)
    with _lock:
        cached = _cache.get(key)
        if cached is not None and (key.startswith("sha256:") or cached[0] is document):
            _cache.move_to_end(key)
            return cached[1]
    index = _build(document)
    with _lock:
        _cache[key] = (document, index)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return index


def forget_operation_indexes() -> None:
    """Drop every cached index. For tests."""
    with _lock:
        _cache.clear()


def _build(document: Mapping[str, Any]) -> OperationIndex:
    operations: list[Operation] = []
    paths = document.get("paths")
    for path, item in (paths or {}).items() if isinstance(paths, Mapping) else ():
        item_at = pointer("paths", path)
        try:
            item, item_at = follow(document, item, item_at)
        except PointerError:
            continue
        if not isinstance(item, Mapping):
            continue
        shared = _parameters(document, item.get("parameters"), child(item_at, "parameters"))
        for method in METHODS:
            raw = item.get(method)
            if isinstance(raw, Mapping):
                at = child(item_at, method)
                operations.append(_operation(document, str(path), method, raw, at, shared))
    by_id = {op.operation_id: op for op in operations if op.operation_id}
    return OperationIndex(
        operations=tuple(operations),
        by_id=by_id,
        by_key={op.key: op for op in operations},
    )


def _operation(
    document: Mapping[str, Any],
    path: str,
    method: str,
    raw: Mapping[str, Any],
    at: str,
    shared: dict[tuple[str, str], Parameter],
) -> Operation:
    own = _parameters(document, raw.get("parameters"), child(at, "parameters"))
    body: Any = raw.get("requestBody")
    if body is not None:
        try:
            body, _ = follow(document, body, child(at, "requestBody"))
        except PointerError:
            body = None
    operation_id = raw.get("operationId")
    tags = raw.get("tags")
    responses = raw.get("responses")
    return Operation(
        method=method.upper(),
        path=path,
        operation_id=operation_id if isinstance(operation_id, str) else None,
        location=at,
        # The operation's own declaration of a parameter overrides the path item's.
        parameters=tuple({**shared, **own}.values()),
        request_body=body if isinstance(body, Mapping) else None,
        responses=responses if isinstance(responses, Mapping) else {},
        tags=tuple(str(tag) for tag in tags) if isinstance(tags, list) else (),
        template=split_template(path),
    )


def _parameters(document: Mapping[str, Any], raw: Any, at: str) -> dict[tuple[str, str], Parameter]:
    found: dict[tuple[str, str], Parameter] = {}
    for position, entry in enumerate(raw if isinstance(raw, list) else ()):
        try:
            entry, _ = follow(document, entry, child(at, position))
        except PointerError:
            continue
        if not isinstance(entry, Mapping) or not isinstance(entry.get("name"), str):
            continue
        location = str(entry.get("in", ""))
        schema = entry.get("schema")
        found[(entry["name"], location)] = Parameter(
            name=entry["name"],
            location=location,
            # A path parameter is always required (OpenAPI 3.x, "Parameter Object").
            required=bool(entry.get("required")) or location == "path",
            schema=schema if isinstance(schema, Mapping) else None,
        )
    return found


def split_template(path: str) -> tuple[tuple[str, str | None], ...]:
    """``/a/{x}/b`` as ``(("/a/", "x"), ("/b", None))``: compiled once per operation."""
    parts: list[tuple[str, str | None]] = []
    end = 0
    for match in _PLACEHOLDER.finditer(path):
        parts.append((path[end : match.start()], match.group(1)))
        end = match.end()
    if end < len(path) or not parts:
        parts.append((path[end:], None))
    return tuple(parts)

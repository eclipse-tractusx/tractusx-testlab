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

"""Validating a value against a schema of an API document, compiled once.

The document is registered as one JSON Schema resource (after the 3.0
translation, :mod:`.schema_dialect`), and a validator for one schema of it is a
``$ref`` to that schema's pointer. Both are cached: the resource per document,
the validator per (document, pointer), each in a bounded LRU — so a sweep that
checks fifty answers against the same error schema compiles it once.

A problem names where it is in the value (a JSON Pointer), the keyword that
failed, where that keyword is in the document
(``#/components/schemas/Material/properties/share/type``, ``$ref`` hops
followed) and a short, masked rendering of the value received.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from tractusx_testlab.logging.masking import mask
from tractusx_testlab.logging.wire.secret_names import is_secret_key
from tractusx_testlab.openapi.conformance.schema_dialect import is_openapi_30, translated_document
from tractusx_testlab.openapi.operations.operation_index import document_key
from tractusx_testlab.openapi.operations.pointers import escape, resolve

#: Documents whose translated resource is kept, and validators kept across them.
DOCUMENTS_CACHED = 16
VALIDATORS_CACHED = 512
#: Problems reported for one value at most; the rest are counted.
MAX_PROBLEMS = 50
#: Characters of a received value a problem quotes.
RECEIVED_CHARS = 80
#: Characters of a validator message kept; its quote of the value can be the whole body.
MESSAGE_CHARS = 400


@dataclass(frozen=True, slots=True)
class SchemaProblem:
    """One way a value does not match its schema."""

    pointer: str
    keyword: str
    schema_location: str
    received: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    def __str__(self) -> str:
        where = self.pointer or "<root>"
        return (
            f"{where}: {self.message} (keyword '{self.keyword}' at {self.schema_location}; "
            f"received {self.received})"
        )


_lock = threading.Lock()
_resources: OrderedDict[str, tuple[Mapping[str, Any], Mapping[str, Any], Registry]] = OrderedDict()
_validators: OrderedDict[tuple[str, str], Any] = OrderedDict()


def schema_problems(document: Mapping[str, Any], schema_at: str, value: Any) -> list[SchemaProblem]:
    """Every way *value* fails the schema at *schema_at* (``#/…``) of *document*."""
    key = document_key(document)
    translated, registry = _resource(document, key)
    validator = _validator(key, schema_at, registry)
    problems: list[SchemaProblem] = []
    errors = validator.iter_errors(value)
    for count, error in enumerate(errors):
        if count == MAX_PROBLEMS:
            remaining = sum(1 for _ in errors) + 1
            problems.append(SchemaProblem("", "", "", "", f"... and {remaining} more"))
            break
        problems.append(_problem(error, translated, key, schema_at))
    return problems


def forget_validators() -> None:
    """Drop every cached resource and validator. For tests."""
    with _lock:
        _resources.clear()
        _validators.clear()


def _uri(key: str) -> str:
    return f"urn:testlab:api:{key.replace(':', '-')}"


def _resource(document: Mapping[str, Any], key: str) -> tuple[Mapping[str, Any], Registry]:
    with _lock:
        cached = _resources.get(key)
        if cached is not None and (key.startswith("sha256:") or cached[0] is document):
            _resources.move_to_end(key)
            return cached[1], cached[2]
    translated = translated_document(document) if is_openapi_30(document) else document
    resource = Resource.from_contents(translated, default_specification=DRAFT202012)
    registry: Registry = Registry().with_resource(_uri(key), resource)
    with _lock:
        _resources[key] = (document, translated, registry)
        _resources.move_to_end(key)
        while len(_resources) > DOCUMENTS_CACHED:
            evicted, _ = _resources.popitem(last=False)
            for stale in [k for k in _validators if k[0] == evicted]:
                del _validators[stale]
    return translated, registry


def _validator(key: str, schema_at: str, registry: Registry) -> Any:
    with _lock:
        cached = _validators.get((key, schema_at))
        if cached is not None and cached[0] is registry:
            _validators.move_to_end((key, schema_at))
            return cached[1]
    validator = jsonschema.Draft202012Validator({"$ref": _uri(key) + schema_at}, registry=registry)
    with _lock:
        _validators[(key, schema_at)] = (registry, validator)
        while len(_validators) > VALIDATORS_CACHED:
            _validators.popitem(last=False)
    return validator


def _problem(
    error: jsonschema.ValidationError, translated: Mapping[str, Any], key: str, schema_at: str
) -> SchemaProblem:
    path = list(error.absolute_path)
    pointer = "".join(f"/{escape(token)}" for token in path)
    message = error.message
    if error.context:
        # The branch that got furthest into the value is the one meant.
        closest = max(error.context, key=lambda e: (len(e.absolute_path), len(e.schema_path)))
        where = "".join(f"/{escape(token)}" for token in closest.absolute_path) or "<root>"
        location = _location(list(closest.absolute_schema_path), translated, key, schema_at)
        message = f"{message}; closest: {where}: {closest.message} (at {location})"
    secret = bool(path) and is_secret_key(str(path[-1]))
    return SchemaProblem(
        pointer=pointer,
        keyword=str(error.validator),
        schema_location=_location(list(error.absolute_schema_path), translated, key, schema_at),
        received="***" if secret else _received(error.instance),
        message=_clipped(str(mask(message)), MESSAGE_CHARS)
        if not secret
        else f"value does not match '{error.validator}'",
    )


def _location(path: list[Any], translated: Mapping[str, Any], key: str, schema_at: str) -> str:
    """Where the failing keyword is in the document, every ``$ref`` hop followed.

    A validator's schema path steps through a ``$ref`` without naming it, so a
    token the current schema does not hold is looked up in its target.
    """
    uri = _uri(key)
    at = schema_at
    try:
        node: Any = resolve(translated, at)
        for token in path:
            for _ in range(MAX_PROBLEMS):
                ref = node.get("$ref") if isinstance(node, Mapping) else None
                if not isinstance(ref, str) or token in node:
                    break
                at = ref[len(uri) :] if ref.startswith(uri) else ref
                node = resolve(translated, at)
            node = node[token] if isinstance(node, Mapping) else node[int(token)]
            at += f"/{escape(token)}"
    except (LookupError, TypeError, ValueError):
        return at or "#"
    return at


def _received(instance: Any) -> str:
    try:
        text = json.dumps(instance, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = repr(instance)
    return _clipped(str(mask(text)), RECEIVED_CHARS)


def _clipped(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"

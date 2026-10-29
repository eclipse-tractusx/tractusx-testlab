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

"""OpenAPI 3.0 schemas as the JSON Schema 2020-12 a validator reads.

OpenAPI 3.1 schemas *are* JSON Schema 2020-12 and are validated as written.
OpenAPI 3.0 schemas are a dialect of draft 4 with three differences that change
a verdict, and each is translated here so a 3.0 document means what it says:

* ``nullable: true`` — ``null`` is allowed too: ``type: string`` becomes
  ``type: [string, "null"]``, an ``enum`` gains ``null``, and a schema without
  a ``type`` (an ``allOf`` around a ``$ref``) becomes ``anyOf: [<it>, {type: null}]``.
* ``exclusiveMinimum`` / ``exclusiveMaximum`` are booleans that qualify
  ``minimum`` / ``maximum``; in 2020-12 they are the bound itself.
* A ``$ref`` replaces its object: keywords beside it are ignored in 3.0, and
  would be applied in 2020-12, so they are dropped.

Everything else (``example``, ``discriminator``, ``xml``, ``x-*``) is an
annotation to a 2020-12 validator and is left alone.

The whole document is translated once — every place OpenAPI 3.0 puts a schema —
so a ``$ref`` from one schema to another lands on a translated schema too.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tractusx_testlab.openapi.operations.operation_index import METHODS

#: Keywords holding one schema, a list of them, or a map of them (OpenAPI 3.0).
_ONE = ("items", "not", "additionalProperties")
_MANY = ("allOf", "anyOf", "oneOf")
_MAP = ("properties", "patternProperties")


def is_openapi_30(document: Mapping[str, Any]) -> bool:
    return str(document.get("openapi", "")).startswith("3.0.")


def to_2020_12(schema: Any) -> Any:
    """One OpenAPI 3.0 schema object, and every schema inside it, as 2020-12."""
    if not isinstance(schema, Mapping):
        return schema
    if isinstance(schema.get("$ref"), str):
        return {"$ref": schema["$ref"]}
    converted: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _ONE:
            converted[key] = to_2020_12(value)
        elif key in _MANY and isinstance(value, list):
            converted[key] = [to_2020_12(item) for item in value]
        elif key in _MAP and isinstance(value, Mapping):
            converted[key] = {name: to_2020_12(item) for name, item in value.items()}
        else:
            converted[key] = value
    _bounds(converted, "exclusiveMinimum", "minimum")
    _bounds(converted, "exclusiveMaximum", "maximum")
    return _nullable(converted)


def _bounds(schema: dict[str, Any], exclusive: str, inclusive: str) -> None:
    flag = schema.get(exclusive)
    if not isinstance(flag, bool):
        return
    del schema[exclusive]
    if flag and inclusive in schema:
        schema[exclusive] = schema.pop(inclusive)


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.pop("nullable", False) is not True:
        return schema
    if "enum" in schema and isinstance(schema["enum"], list) and None not in schema["enum"]:
        schema["enum"] = [*schema["enum"], None]
    kind = schema.get("type")
    if isinstance(kind, str):
        schema["type"] = [kind, "null"]
        return schema
    if isinstance(kind, list):
        schema["type"] = kind if "null" in kind else [*kind, "null"]
        return schema
    return {"anyOf": [schema, {"type": "null"}]}


def translated_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """*document* as plain data with every schema translated (3.0 documents only)."""
    copy: dict[str, Any] = _thaw(document)
    components = copy.get("components")
    if isinstance(components, dict):
        _each(
            components.get("schemas"),
            lambda name, s, holder: holder.__setitem__(name, to_2020_12(s)),
        )
        _each(components.get("parameters"), lambda _n, p, _h: _parameter(p))
        _each(components.get("headers"), lambda _n, h, _h: _parameter(h))
        _each(components.get("responses"), lambda _n, r, _h: _response(r))
        _each(components.get("requestBodies"), lambda _n, b, _h: _content(b))
    paths = copy.get("paths")
    for item in paths.values() if isinstance(paths, dict) else ():
        if not isinstance(item, dict):
            continue
        _parameters(item.get("parameters"))
        for method in METHODS:
            operation = item.get(method)
            if isinstance(operation, dict):
                _parameters(operation.get("parameters"))
                _content(operation.get("requestBody"))
                _each(operation.get("responses"), lambda _n, r, _h: _response(r))
    return copy


def _each(holder: Any, apply: Any) -> None:
    if isinstance(holder, dict):
        for name, value in list(holder.items()):
            if isinstance(value, dict):
                apply(name, value, holder)


def _parameters(entries: Any) -> None:
    for entry in entries if isinstance(entries, list) else ():
        _parameter(entry)


def _parameter(entry: Any) -> None:
    if isinstance(entry, dict):
        if isinstance(entry.get("schema"), dict):
            entry["schema"] = to_2020_12(entry["schema"])
        _content(entry)


def _response(response: Any) -> None:
    if isinstance(response, dict):
        _content(response)
        _each(response.get("headers"), lambda _n, h, _h: _parameter(h))


def _content(holder: Any) -> None:
    content = holder.get("content") if isinstance(holder, dict) else None
    _each(content, lambda _n, media, _h: _parameter(media))


def _thaw(value: Any) -> Any:
    """A plain, mutable copy of a (read-only) document."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    return value

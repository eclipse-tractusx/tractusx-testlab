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

"""Reading an API file as the type its entry declares, into plain JSON data.

An OpenAPI document is JSON data whichever way it is written, so a file is read
into exactly what JSON can hold — mappings with string keys, lists, strings,
finite numbers, booleans and ``null`` — and refused with the line to fix when
it holds anything else:

* **YAML** is read with PyYAML's safe loader (the libyaml one when available),
  narrowed further: no tag outside JSON's (``!!timestamp``, ``!!binary``,
  ``!!set``, ``!!python/…`` are refused, and an unquoted date stays text), no
  duplicate key, no key that is not a string or an integer (a status code
  written ``200:`` is read as ``"200"``), no ``.nan`` or ``.inf``.
* **JSON** is read strictly: no duplicate key and no ``NaN`` / ``Infinity``,
  which Python's parser otherwise accepts.

Nothing here follows a reference or opens another file; that is
:mod:`~tractusx_testlab.openapi.ref_walk`, and it refuses to.
"""

from __future__ import annotations

import json
import math
from collections.abc import Hashable
from typing import TYPE_CHECKING, Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node, ScalarNode

#: Media types read as YAML, and as JSON (ADR-0030).
YAML_TYPES = frozenset({"application/vnd.oai.openapi", "application/yaml"})
JSON_TYPES = frozenset({"application/vnd.oai.openapi+json", "application/json"})

_TIMESTAMP = "tag:yaml.org,2002:timestamp"
_MERGE = "tag:yaml.org,2002:merge"
#: Tags SafeLoader knows and JSON cannot hold.
_NON_JSON_TAGS = (
    _TIMESTAMP,
    "tag:yaml.org,2002:binary",
    "tag:yaml.org,2002:set",
    "tag:yaml.org,2002:omap",
    "tag:yaml.org,2002:pairs",
)


class ParseError(ValueError):
    """The file is not the JSON data its declared type says it is."""


def parse(data: bytes, media_type: str) -> Any:
    """*data* read as *media_type* — YAML or JSON — into plain JSON data.

    Raises:
        ParseError: naming what is wrong and, where the parser knows, the line.
    """
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError(f"is not UTF-8 text (invalid byte at offset {exc.start})") from None
    try:
        if media_type in JSON_TYPES:
            return _json(text)
        if media_type in YAML_TYPES:
            return _yaml(text)
    except RecursionError:
        raise ParseError("nests too deeply to read") from None
    raise ParseError(f"has an unknown type '{media_type}'")


def _json(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=_no_constant)
    except json.JSONDecodeError as exc:
        raise ParseError(
            f"is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from None


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key, value in pairs:
        if key in mapping:
            raise ParseError(f"is not valid JSON: duplicate key '{key}'")
        mapping[key] = value
    return mapping


def _no_constant(name: str) -> Any:
    raise ParseError(f"is not valid JSON: '{name}' is not a JSON number")


def _yaml(text: str) -> Any:
    try:
        return yaml.load(text, Loader=_JsonYamlLoader)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        raise ParseError(f"is not valid YAML: {exc.problem or exc.context}{where}") from None
    except yaml.YAMLError as exc:
        raise ParseError(f"is not valid YAML: {exc}") from None


if TYPE_CHECKING:
    _SafeLoader = yaml.SafeLoader
else:  # libyaml's loader when PyYAML was built with it: the same rules, in C.
    _SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class _JsonYamlLoader(_SafeLoader):
    """The safe loader, narrowed to what JSON can hold."""

    # Copied before narrowing: the class attribute is shared with SafeLoader.
    yaml_implicit_resolvers = {
        first: [(tag, regexp) for tag, regexp in resolvers if tag != _TIMESTAMP]
        for first, resolvers in _SafeLoader.yaml_implicit_resolvers.items()
    }

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        """A mapping with unique keys, every one of them text."""
        seen: set[tuple[str, str]] = set()
        for key_node, _ in node.value:
            if isinstance(key_node, ScalarNode) and key_node.tag != _MERGE:
                if (key_node.tag, key_node.value) in seen:
                    raise ConstructorError(
                        None, None, f"duplicate key '{key_node.value}'", key_node.start_mark
                    )
                seen.add((key_node.tag, key_node.value))
        mapping: dict[Hashable, Any] = {}
        for key, value in super().construct_mapping(node, deep=deep).items():
            if isinstance(key, bool) or not isinstance(key, str | int):
                raise ConstructorError(
                    None,
                    None,
                    f"key {key!r} is not text; quote it",
                    node.start_mark,
                )
            if str(key) in mapping:
                raise ConstructorError(None, None, f"duplicate key '{key}'", node.start_mark)
            mapping[str(key)] = value
        return mapping

    def construct_yaml_float(self, node: ScalarNode) -> float:
        """A float JSON can hold — not ``.nan`` or ``.inf``."""
        value: float = super().construct_yaml_float(node)
        if not math.isfinite(value):
            raise ConstructorError(
                None, None, f"'{node.value}' is not a JSON number", node.start_mark
            )
        return value

    def refuse_tag(self, node: Node) -> Any:
        """A tag JSON has no value for."""
        raise ConstructorError(
            None, None, f"tag '{node.tag}' is not allowed in an API file", node.start_mark
        )


_JsonYamlLoader.add_constructor("tag:yaml.org,2002:float", _JsonYamlLoader.construct_yaml_float)
for _tag in _NON_JSON_TAGS:
    _JsonYamlLoader.add_constructor(_tag, _JsonYamlLoader.refuse_tag)

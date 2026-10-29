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

"""Walking a parsed API document once: its size, its shape and its ``$ref``\\ s.

An API file is the TCK's, but it is somebody else's document, and it travels
with the package to every engine that runs it. One walk, before anything else
reads it, bounds what that document can cost and checks what it points at:

* **Size after aliases.** A YAML alias shares a node instead of copying it, so
  a few lines can stand for billions of nodes to any reader that walks them
  ("billion laughs"). The walk counts every node it visits, aliases included,
  and stops at :data:`MAX_NODES`. An alias that contains itself is refused.
* **Depth.** No mapping or list nested deeper than :data:`MAX_DEPTH`.
* **References.** Every ``$ref`` is internal — ``#`` followed by a JSON
  pointer — and names something in the document. An external one (another file,
  a URL) is refused rather than followed: following it is a network call or a
  file read at compile time, on a name the document chose. A chain of
  references that comes back to where it started resolves to nothing and is
  refused too; a schema that refers to itself *inside* (a tree node with
  children) is ordinary and allowed.

What is skipped is what holds literal data, not OpenAPI: ``example``,
``default``, ``enum``, ``const``, an Example Object's ``value``, a schema's
list of ``examples`` and every ``x-`` extension — a ``$ref`` key in a sample
payload is part of the sample.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum, auto
from typing import Any
from urllib.parse import unquote

#: Most nodes one document may have, every alias counted where it is used.
MAX_NODES = 1_000_000
#: Deepest nesting of mappings and lists.
MAX_DEPTH = 128
#: Longest chain of references to references.
MAX_REF_CHAIN = 32
#: Most problems reported for one document; the rest are counted.
MAX_PROBLEMS = 20

_REF = "$ref"
#: Keys whose value is literal data, never OpenAPI.
_LITERAL_KEYS = frozenset({"example", "default", "enum", "const"})
#: Keys whose mapping is keyed by names an author chose — a schema called
#: ``default``, a property called ``example`` — not by keywords.
_NAME_MAPS = frozenset(
    {
        # JSON Schema
        "properties",
        "patternProperties",
        "$defs",
        "definitions",
        "dependentSchemas",
        # OpenAPI
        "paths",
        "webhooks",
        "schemas",
        "responses",
        "parameters",
        "requestBodies",
        "headers",
        "securitySchemes",
        "links",
        "callbacks",
        "pathItems",
        "content",
        "encoding",
        "variables",
    }
)
_EXAMPLES = "examples"
#: Marks the point at which the walk leaves a container.
_LEAVE = object()


class DocumentShapeError(ValueError):
    """The document is too large, too deep or contains itself."""


def reference_problems(document: Any) -> list[str]:
    """Every problem with the ``$ref``\\ s in *document*, each naming where it sits.

    Each problem completes "the file …", like every problem
    :class:`~tractusx_testlab.openapi.document.ApiDocumentError` reports.

    Raises:
        DocumentShapeError: before any reference is checked, when the document
            exceeds :data:`MAX_NODES` or :data:`MAX_DEPTH` or contains itself.
    """
    problems: list[str] = []
    checked: dict[str, str | None] = {}
    for at, ref in _references(document):
        if ref not in checked:
            checked[ref] = _problem(document, ref)
        if checked[ref] is not None:
            problems.append(f"has $ref '{ref}' at {at or '/'} that {checked[ref]}")
    if len(problems) > MAX_PROBLEMS:
        hidden = len(problems) - MAX_PROBLEMS
        problems = [*problems[:MAX_PROBLEMS], f"…and {hidden} more $ref problems"]
    return problems


class _Role(Enum):
    """What a mapping is, which decides which of its keys are keywords."""

    #: An OpenAPI or JSON Schema object: its keys are keywords.
    OBJECT = auto()
    #: Keyed by names an author chose (``properties``): no key is a keyword.
    NAMES = auto()
    #: ``examples`` keyed by name: each value is an Example Object.
    EXAMPLES = auto()
    #: An Example Object: its ``value`` is the sample.
    EXAMPLE = auto()


def _references(document: Any) -> Iterator[tuple[str, str]]:
    """``(JSON pointer, $ref)`` for every reference, in document order.

    Iterative, with each container entered and left explicitly, so the walk
    knows which containers it is inside of — which is how an alias that
    contains itself is told apart from one that is merely used twice.
    """
    nodes = 0
    inside: set[int] = set()
    # (node, pointer, depth, role), or (_LEAVE, id) once a container's children are done.
    stack: list[tuple[Any, ...]] = [(document, "", 0, _Role.OBJECT)]
    while stack:
        entry = stack.pop()
        if entry[0] is _LEAVE:
            inside.discard(entry[1])
            continue
        node, pointer, depth, role = entry
        nodes += 1
        if nodes > MAX_NODES:
            raise DocumentShapeError(f"has more than {MAX_NODES:,} nodes once its aliases expand")
        if not isinstance(node, dict | list):
            continue
        if id(node) in inside:
            raise DocumentShapeError(
                f"contains itself at {pointer or '/'} (a recursive YAML alias)"
            )
        if depth >= MAX_DEPTH:
            raise DocumentShapeError(f"nests deeper than {MAX_DEPTH} levels at {pointer}")
        inside.add(id(node))
        stack.append((_LEAVE, id(node)))
        if isinstance(node, list):
            stack.extend(
                (item, f"{pointer}/{index}", depth + 1, _Role.OBJECT)
                for index, item in reversed(list(enumerate(node)))
            )
            continue
        keyed_by_name = role in (_Role.NAMES, _Role.EXAMPLES)
        if not keyed_by_name and isinstance(node.get(_REF), str):
            yield pointer, node[_REF]
        for key, value in reversed(list(node.items())):
            if not keyed_by_name and _is_literal(key, value, role):
                continue
            stack.append((value, f"{pointer}/{_escape(key)}", depth + 1, _child_role(key, role)))


def _child_role(key: str, role: _Role) -> _Role:
    """The role of the value under *key* of a mapping with *role*."""
    if role is _Role.EXAMPLES:
        return _Role.EXAMPLE
    if role is _Role.NAMES:
        return _Role.OBJECT
    if key == _EXAMPLES:
        return _Role.EXAMPLES
    return _Role.NAMES if key in _NAME_MAPS else _Role.OBJECT


def _is_literal(key: str, value: Any, role: _Role) -> bool:
    """Whether *key* of a mapping with *role* holds sample data rather than OpenAPI."""
    if key in _LITERAL_KEYS or key.startswith("x-"):
        return True
    # 3.1: a schema's `examples` is a list of samples; an Example Object's
    # `value` is its sample.
    return (key == _EXAMPLES and isinstance(value, list)) or (
        role is _Role.EXAMPLE and key == "value"
    )


def _problem(document: Any, ref: str) -> str | None:
    """What is wrong with *ref*, or ``None`` when it resolves to a value."""
    seen = [ref]
    current = ref
    while True:
        if not current.startswith("#"):
            return (
                "points outside the file; an API file must be self-contained — "
                "bundle it into one file first"
                if current == ref
                else None  # reported where that reference itself sits
            )
        found, target = _resolve(document, current)
        if not found:
            return "names nothing in the file" if current == ref else None
        following = target.get(_REF) if isinstance(target, dict) else None
        if not isinstance(following, str):
            return None
        if following in seen:
            return f"is circular: {' → '.join([*seen, following])}"
        seen.append(following)
        if len(seen) > MAX_REF_CHAIN:
            return f"is a chain of more than {MAX_REF_CHAIN} references"
        current = following


def _resolve(document: Any, ref: str) -> tuple[bool, Any]:
    """``(True, value)`` for the value the internal *ref* points at, else ``(False, None)``."""
    pointer = unquote(ref[1:])
    if not pointer:
        return True, document
    if not pointer.startswith("/"):
        return False, None
    node = document
    for token in pointer[1:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            return False, None
    return True, node


def _escape(key: str) -> str:
    """*key* as a JSON pointer token (RFC 6901)."""
    return key.replace("~", "~0").replace("/", "~1")

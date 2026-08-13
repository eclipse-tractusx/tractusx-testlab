#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Path extraction utilities for navigating nested dicts/lists/StepOutput objects."""

from __future__ import annotations

import re
from typing import Any, Optional

# Matches a path segment with a predicate filter: ``name[key=value]``
_PREDICATE_RE = re.compile(r"^([^\[]+)\[([^=\]]+)=([^\]]*)\]$")
_SENTINEL = object()


def _snake_to_camel(name: str) -> str:
    """Convert ``snake_case`` to ``camelCase``."""
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _dict_get(d: dict, key: str) -> Any:
    """Get value from dict, trying original key first, then camelCase fallback."""
    if key in d:
        return d[key]
    camel = _snake_to_camel(key)
    if camel != key and camel in d:
        return d[camel]
    return None


def _match_predicate_value(actual: Any, expected: str) -> bool:
    """Return ``True`` when *actual* is semantically equal to the predicate string.

    Quoted values (``'...'``) are compared as exact strings.
    Unquoted values use type coercion (booleans case-insensitive, numbers by
    string representation).
    """
    if actual is None:
        return False
    # Quoted value → exact string comparison
    if len(expected) >= 2 and expected[0] == "'" and expected[-1] == "'":
        return str(actual) == expected[1:-1]
    # Unquoted → type-coerced comparison
    if isinstance(actual, str):
        return actual == expected
    if isinstance(actual, bool):
        return str(actual).lower() == expected.lower()
    return str(actual) == expected


def _iter_predicate_values(item: Any, key: str) -> Any:
    """Yield every value reachable at *key* within *item*, fanning out over lists.

    *key* may be a dotted path rather than a single field, so an element can be
    selected by a nested property: ``endpoints.interface`` matches when **any**
    endpoint carries the interface, and ``semanticId.keys.value`` reaches into
    the AAS reference structure.  Intermediate lists fan out rather than
    requiring an index, which is what gives the match its "any" semantics.
    """
    current: list[Any] = [item]
    for segment in _split_path(key):
        following: list[Any] = []
        for node in current:
            if isinstance(node, dict):
                value = _dict_get(node, segment)
                if value is not None:
                    following.append(value)
            elif isinstance(node, list):
                if segment.isdigit():
                    index = int(segment)
                    if index < len(node):
                        following.append(node[index])
                    continue
                for element in node:
                    if isinstance(element, dict):
                        value = _dict_get(element, segment)
                        if value is not None:
                            following.append(value)
        if not following:
            return
        current = following
    yield from current


def _find_by_predicate(items: list, key: str, value: str) -> Any:
    """Return the first element in *items* whose *key* matches *value*."""
    for item in items:
        for candidate in _iter_predicate_values(item, key):
            if _match_predicate_value(candidate, value):
                return item
    return None


def _split_path(path: str) -> list[str]:
    """Split *path* on dots, ignoring dots nested inside ``[...]`` predicates.

    A predicate value routinely contains dots — semantic IDs and interface
    names such as ``endpoints[interface='SUBMODEL-VALUE-3.1']`` are the common
    case — so a naive ``path.split(".")`` shreds the segment and the lookup
    silently yields ``None``.
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in path:
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)
        if char == "." and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [part for part in parts if part]


def _traverse_dict(data: Any, path: str) -> Any:
    """Walk a nested dict/list structure along a dot-separated *path*."""
    current: Any = data
    for part in _split_path(path):
        if current is None:
            return None
        current = _resolve_path_segment(current, part)
    return current


def _resolve_path_segment(current: Any, part: str) -> Any:
    """Resolve a single path segment against the current value."""
    m = _PREDICATE_RE.match(part)
    if m:
        name, pred_key, pred_val = m.group(1), m.group(2), m.group(3)
        # When the current value is itself a list, apply the predicate to each
        # element's container in turn.  This lets a path step over an
        # intermediate array without naming an index:
        # ``submodelDescriptors.endpoints[interface='…']``.
        if isinstance(current, list):
            for element in current:
                found = _resolve_path_segment(element, part)
                if found is not None:
                    return found
            return None
        container = _dict_get(current, name) if isinstance(current, dict) else None
        if not isinstance(container, list):
            return None
        return _find_by_predicate(container, pred_key, pred_val)
    if isinstance(current, dict):
        return _dict_get(current, part)
    if isinstance(current, list) and part.isdigit():
        idx = int(part)
        return current[idx] if idx < len(current) else None
    return None


#: Names every step output carries whatever it declares — the ``StepOutput``
#: slots and the response fields a script can always assert on.
UNIVERSAL_RETURNS = frozenset({
    "value", "request", "response",
    "status_code", "headers", "body", "duration_ms",
    "response_body", "response_headers",
})


def declared_names(step_cls: Any) -> frozenset[str]:
    """Every name a ``returns:`` block may read off *step_cls*.

    A step's declared models are its public surface, so what a script can name
    is what those models declare, plus the slots every output carries. Anything
    else is a typo or a guess at the step's internals, and resolving it would
    turn either into a silent ``None`` three steps later.
    """
    names = set(UNIVERSAL_RETURNS)
    model = getattr(step_cls, "output_model", None)
    fields = getattr(model, "model_fields", None) or {}
    for name, field in fields.items():
        names.add(name)
        if getattr(field, "alias", None):
            names.add(field.alias)
    return frozenset(names)


def extract_path(
    output: Any, path: Optional[str], declared: Optional[frozenset[str]] = None
) -> Any:
    """Extract a value from a nested dict/list/object using dot-separated *path*.

    Supports predicate-based array filtering: ``items[key='value']``
    selects the first element in the ``items`` list whose ``key`` field
    equals ``value``.

    When *declared* is given, a first segment outside it does not resolve: the
    step said what it produces, and a name it never declared must not quietly
    come back from the response internals.
    """
    if path is None:
        return output

    from tractusx_testlab.steps.base import StepOutput as _SO
    if isinstance(output, _SO):
        return _extract_from_step_output(output, path, declared)

    if isinstance(output, dict):
        return _traverse_dict(output, path)
    return getattr(output, path, None)


def _extract_from_step_output(
    output: Any, path: str, declared: Optional[frozenset[str]] = None
) -> Any:
    """Extract a value from a StepOutput by resolving the first segment then traversing."""
    segments = _split_path(path)
    first = segments[0] if segments else path
    rest = ".".join(segments[1:]) if len(segments) > 1 else None

    resolved = _resolve_first_segment(output, first, rest, path, declared)

    # If there's a remaining path and resolved is navigable, continue.  Lists
    # count as navigable: the remaining path may index into them (``0.id``) or
    # filter them (``[interface='…']``).
    if rest and resolved is not None:
        if isinstance(resolved, (dict, list)):
            return _traverse_dict(resolved, rest)
        return getattr(resolved, rest, None)

    # Final fallback: full dot-path traversal on value dict
    if resolved is None and isinstance(output.value, dict):
        return _traverse_dict(output.value, path)
    return resolved


def _resolve_first_segment(
    output: Any,
    first: str,
    rest: Optional[str],
    full_path: str,
    declared: Optional[frozenset[str]] = None,
) -> Any:
    """Resolve the first path segment against a StepOutput's various data sources."""
    # Map well-known aliases
    if first == "response_body":
        resolved = _resolve_response_body(output)
    elif first == "response_headers":
        resolved = _resolve_response_headers(output)
    elif isinstance(output.value, dict):
        resolved = _resolve_from_value_dict(output, first, rest, full_path)
    else:
        resolved = None

    if resolved is not None:
        return resolved

    if declared is not None and first not in declared:
        # The step never declared this name; reaching into its response for
        # something that happens to share the spelling is how a script ends up
        # asserting on a value no step promised.
        return None

    # Fall back through response attrs → response body dict → StepOutput slots
    return _fallback_resolution(output, first)


def _resolve_response_body(output: Any) -> Any:
    """Resolve the 'response_body' alias."""
    if output.value is not None:
        return output.value
    return output.response.body if output.response else None

def _resolve_response_headers(output: Any) -> Any:
    """Resolve the 'response_headers' alias to the response's headers dict."""
    return output.response.headers if output.response else None

def _fallback_resolution(output: Any, first: str) -> Any:
    """Try response attrs, response body dict, and StepOutput slots in order."""
    if output.response is not None:
        resp_val = getattr(output.response, first, _SENTINEL)
        if resp_val is not _SENTINEL:
            return resp_val

    if output.response is not None and isinstance(output.response.body, dict):
        body_val = output.response.body.get(first)
        if body_val is not None:
            return body_val

    slot_val = getattr(output, first, _SENTINEL)
    if slot_val is not _SENTINEL:
        return slot_val

    return None


def _resolve_from_value_dict(output: Any, first: str, rest: Optional[str], full_path: str) -> Any:
    """Try to resolve the first segment from the StepOutput.value dict."""
    # _resolve_path_segment handles both plain keys and ``name[key=value]``
    # predicates, so a filtered first segment resolves here rather than
    # falling through to the whole-path retry below.
    result = _resolve_path_segment(output.value, first)
    if result is not None:
        return result
    if not rest and ("." in full_path or "[" in full_path):
        return _traverse_dict(output.value, full_path)
    return None

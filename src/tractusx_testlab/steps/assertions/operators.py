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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""The operator vocabulary — the one table every comparison in a run goes through.

A ``validate:`` assertion and a ``flow/if`` condition ask the same question of a
value, so they resolve the same operator names here rather than each keeping a
table that would drift from the other.
"""

from __future__ import annotations

import re
from typing import Literal, get_args

#: Every operator a TCK may name, ratified in specification §5.4. This type is
#: the vocabulary — step params annotate with it, and the sets below derive
#: from it, so there is nowhere for a second list of operators to drift into.
AssertOperator = Literal[
    "not_null",
    "is_null",
    "not_empty",
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "matches_regex",
    "one_of",
    "none_of",
    "has_key",
    "not_has_key",
    "gt",
    "gte",
    "lt",
    "lte",
    "length_equals",
    "length_gt",
    "length_lt",
    "between",
]

OPERATORS: frozenset[str] = frozenset(get_args(AssertOperator))

#: Operators that take no ``value``; giving one is meaningless, not an error.
UNARY_OPERATORS = frozenset({"not_null", "is_null", "not_empty"})

#: Operators that read ``min``/``max`` instead of ``value``.
RANGE_OPERATORS = frozenset({"between"})

_MEMBERSHIP_OPERATORS = frozenset({"one_of", "none_of", "has_key", "not_has_key"})
_ORDERING_OPERATORS = frozenset({"gt", "gte", "lt", "lte"})
_SIZE_OPERATORS = frozenset({"length_equals", "length_gt", "length_lt"})
_DIRECT_OPERATORS = UNARY_OPERATORS | {
    "equals", "not_equals", "contains", "not_contains", "matches_regex",
}

# Every operator must land in exactly one dispatch group. A name declared above
# but never routed would fail at runtime as "unknown", which is the confusing
# way to find out that the two halves of this module disagree.
_DISPATCH_GROUPS = (
    _DIRECT_OPERATORS, _MEMBERSHIP_OPERATORS,
    _ORDERING_OPERATORS, _SIZE_OPERATORS, RANGE_OPERATORS,
)
assert OPERATORS == frozenset().union(*_DISPATCH_GROUPS), (
    "operator vocabulary and dispatch groups disagree: "
    f"{OPERATORS ^ frozenset().union(*_DISPATCH_GROUPS)}"
)


def apply_operator(operator: str, actual: object, expected: object) -> tuple[bool, str]:
    """Compare *actual* against *expected* under *operator*.

    Returns whether the comparison held and, when it did not, a message saying
    what was wanted and what arrived. An operator outside :data:`OPERATORS`
    fails loudly rather than quietly passing something else off as the check.
    """
    if operator in _DIRECT_OPERATORS:
        return _apply_direct_operator(operator, actual, expected)
    if operator in _MEMBERSHIP_OPERATORS:
        return _apply_membership_operator(operator, actual, expected)
    if operator in _ORDERING_OPERATORS:
        return _apply_ordering_operator(operator, actual, expected)
    if operator in _SIZE_OPERATORS:
        return _apply_size_operator(operator, actual, expected)
    if operator in RANGE_OPERATORS:
        return _apply_range_operator(actual, expected)
    return False, (
        f"Unknown operator {operator!r}. Known operators: {', '.join(sorted(OPERATORS))}"
    )


def _apply_direct_operator(
    operator: str, actual: object, expected: object
) -> tuple[bool, str]:
    """Apply the null, emptiness, equality and text operators."""
    if operator == "not_null":
        return actual is not None, "Expected non-null value, got None"
    if operator == "is_null":
        return actual is None, f"Expected null, got {actual!r}"
    if operator == "not_empty":
        return bool(actual), f"Expected non-empty value, got {actual!r}"
    if operator == "equals":
        passed = actual == expected or str(actual) == str(expected)
        return passed, f"Expected {expected!r}, got {actual!r}"
    if operator == "not_equals":
        passed = actual != expected and str(actual) != str(expected)
        return passed, f"Expected value != {expected!r}, got {actual!r}"
    if operator == "contains":
        passed = str(expected) in str(actual) if actual is not None else False
        return passed, f"Expected {actual!r} to contain {expected!r}"
    if operator == "not_contains":
        passed = str(expected) not in str(actual) if actual is not None else True
        return passed, f"Expected {actual!r} to NOT contain {expected!r}"
    passed = isinstance(actual, str) and bool(re.search(str(expected), actual))
    return passed, f"Pattern {expected!r} not matched in {actual!r}"


def _apply_membership_operator(
    operator: str, actual: object, expected: object
) -> tuple[bool, str]:
    """Apply the operators that ask whether something is part of something else."""
    if operator == "one_of":
        allowed = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return actual in allowed, f"Expected {actual!r} to be one of {expected!r}"
    if operator == "none_of":
        excluded = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return actual not in excluded, f"Expected {actual!r} to be none of {expected!r}"
    has_key = isinstance(actual, dict) and expected in actual
    if operator == "has_key":
        return has_key, f"Expected {actual!r} to have key {expected!r}"
    return not has_key, f"Expected {actual!r} to NOT have key {expected!r}"


def _apply_ordering_operator(
    operator: str, actual: object, expected: object
) -> tuple[bool, str]:
    """Apply the numeric comparisons, treating a non-number as "does not compare"."""
    try:
        left, right = float(actual), float(expected)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False, f"Cannot compare {actual!r} with {expected!r} numerically"
    comparisons = {
        "gt": left > right,
        "gte": left >= right,
        "lt": left < right,
        "lte": left <= right,
    }
    return comparisons[operator], f"Expected {actual!r} {operator} {expected!r}"


def _apply_size_operator(
    operator: str, actual: object, expected: object
) -> tuple[bool, str]:
    """Apply the length comparisons, treating a sizeless value as "no length"."""
    try:
        length = len(actual)  # type: ignore[arg-type]
        wanted = int(expected)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False, f"Cannot measure the length of {actual!r} against {expected!r}"
    comparisons = {
        "length_equals": length == wanted,
        "length_gt": length > wanted,
        "length_lt": length < wanted,
    }
    return comparisons[operator], f"Expected length {length} {operator} {wanted}"


def _apply_range_operator(actual: object, expected: object) -> tuple[bool, str]:
    """Check that *actual* falls within the ``[min, max]`` pair in *expected*."""
    bounds = expected if isinstance(expected, (list, tuple)) else (None, None)
    if len(bounds) != 2 or bounds[0] is None or bounds[1] is None:
        return False, "'between' needs both a 'min' and a 'max'"
    try:
        value, low, high = float(actual), float(bounds[0]), float(bounds[1])  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False, f"Cannot place {actual!r} between {bounds[0]!r} and {bounds[1]!r}"
    return low <= value <= high, (
        f"Expected {actual!r} to be between {bounds[0]!r} and {bounds[1]!r}"
    )

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""The operator vocabulary — the one table every comparison in a run goes through.

A ``validate:`` assertion and a ``flow/if`` condition ask the same question of a
value, so they resolve the same operator names here rather than each keeping a
table that would drift from the other.

An operator is a row in :data:`_TABLE`: a name, the shape of operands it reads,
the comparison itself, and how its failure reads. Applying one is a dictionary
lookup followed by a single call — a name that is not in the table is the only
branch, because an unknown operator must never be mistaken for a check that
held. Operands that do not fit the operator (a missing bound, a non-number, a
value with no length) raise :class:`OperandError` from the comparison and come
back as a failure that names the problem.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal, get_args

#: Every operator a TCK may name, ratified in specification §5.4. This type is
#: the vocabulary — step params annotate with it, and the table below is checked
#: against it, so there is nowhere for a second list of operators to drift into.
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


class Arity(Enum):
    """Which operands an operator reads — the authoring contract of its params."""

    #: Reads only the value under test; a ``value`` would mean nothing.
    UNARY = "unary"
    #: Reads the value under test and ``value``.
    BINARY = "binary"
    #: Reads the value under test and the ``min``/``max`` pair.
    RANGE = "range"


class OperandError(ValueError):
    """The operands do not fit the operator.

    Raised by a comparison that cannot even be attempted — a bound that was
    never given, a word where a number belongs, a pattern that is not a regular
    expression. :func:`apply_operator` turns it into a failure carrying this
    message, so a malformed check reads as a rejected check and never as a
    passing one.
    """


#: A comparison, once its operands have been shaped: takes the value under test
#: and what it is compared against, answers whether the check held.
Check = Callable[[object, object], bool]


# ---------------------------------------------------------------------------
# Operand shaping — each adapter turns one family of raw operands into the
# arguments its comparison actually wants, and rejects the pairs that cannot.
# ---------------------------------------------------------------------------


def _numeric(compare: Callable[[float, float], bool]) -> Check:
    """Read both operands as numbers before *compare* sees them."""

    def check(actual: object, expected: object) -> bool:
        try:
            left, right = float(actual), float(expected)  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise OperandError(
                f"Cannot compare {actual!r} with {expected!r} numerically"
            ) from error
        return compare(left, right)

    return check


def _sized(compare: Callable[[int, int], bool]) -> Check:
    """Measure the value under test and read the expectation as a count."""

    def check(actual: object, expected: object) -> bool:
        try:
            length = len(actual)  # type: ignore[arg-type]
            if not isinstance(expected, (int, float, str)):
                raise TypeError(f"not a count: {expected!r}")
            wanted = int(expected)
        except (TypeError, ValueError) as error:
            raise OperandError(
                f"Cannot measure the length of {actual!r} against {expected!r}"
            ) from error
        return compare(length, wanted)

    return check


def _bounded(compare: Callable[[float, float, float], bool]) -> Check:
    """Split the expectation into the ``[min, max]`` pair a range check needs."""

    def check(actual: object, expected: object) -> bool:
        bounds = expected if isinstance(expected, (list, tuple)) else ()
        if len(bounds) != 2 or bounds[0] is None or bounds[1] is None:
            raise OperandError("A range check needs both a 'min' and a 'max'")
        try:
            value, low, high = float(actual), float(bounds[0]), float(bounds[1])  # type: ignore[arg-type]
        except (TypeError, ValueError) as error:
            raise OperandError(
                f"Cannot place {actual!r} between {bounds[0]!r} and {bounds[1]!r}"
            ) from error
        return compare(value, low, high)

    return check


def _is_member(actual: object, expected: object) -> bool:
    """Ask whether *actual* is in *expected*, a lone value standing for a set of one."""
    allowed = expected if isinstance(expected, (list, tuple, set)) else (expected,)
    try:
        return actual in allowed
    except TypeError as error:
        raise OperandError(f"Cannot look for {actual!r} inside {expected!r}") from error


def _has_key(actual: object, expected: object) -> bool:
    """Ask whether *actual* is a mapping carrying the key *expected*."""
    if not isinstance(actual, dict):
        return False
    try:
        return expected in actual
    except TypeError as error:
        raise OperandError(f"{expected!r} cannot be used as a key") from error


def _matches(actual: object, expected: object) -> bool:
    """Search *actual* for the pattern *expected*, which only text can satisfy."""
    if not isinstance(actual, str):
        return False
    try:
        return re.search(str(expected), actual) is not None
    except re.error as error:
        raise OperandError(f"{expected!r} is not a valid regular expression") from error


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Operator:
    """One row of the operator table.

    *message* is a format template read only when the check fails, so a passing
    assertion never pays to describe a failure that did not happen. It may name
    ``{actual}`` and ``{expected}``.
    """

    name: str
    arity: Arity
    check: Check
    message: str


_TABLE: tuple[Operator, ...] = (
    Operator(
        "not_null", Arity.UNARY,
        lambda actual, _expected: actual is not None,
        "Expected a non-null value, got {actual!r}",
    ),
    Operator(
        "is_null", Arity.UNARY,
        lambda actual, _expected: actual is None,
        "Expected null, got {actual!r}",
    ),
    Operator(
        "not_empty", Arity.UNARY,
        lambda actual, _expected: bool(actual),
        "Expected a non-empty value, got {actual!r}",
    ),
    Operator(
        "equals", Arity.BINARY,
        lambda actual, expected: actual == expected or str(actual) == str(expected),
        "Expected {expected!r}, got {actual!r}",
    ),
    Operator(
        "not_equals", Arity.BINARY,
        lambda actual, expected: actual != expected and str(actual) != str(expected),
        "Expected a value other than {expected!r}, got {actual!r}",
    ),
    Operator(
        "contains", Arity.BINARY,
        lambda actual, expected: actual is not None and str(expected) in str(actual),
        "Expected {actual!r} to contain {expected!r}",
    ),
    Operator(
        "not_contains", Arity.BINARY,
        lambda actual, expected: actual is None or str(expected) not in str(actual),
        "Expected {actual!r} to NOT contain {expected!r}",
    ),
    Operator(
        "matches_regex", Arity.BINARY,
        _matches,
        "Pattern {expected!r} not matched in {actual!r}",
    ),
    Operator(
        "one_of", Arity.BINARY,
        _is_member,
        "Expected {actual!r} to be one of {expected!r}",
    ),
    Operator(
        "none_of", Arity.BINARY,
        lambda actual, expected: not _is_member(actual, expected),
        "Expected {actual!r} to be none of {expected!r}",
    ),
    Operator(
        "has_key", Arity.BINARY,
        _has_key,
        "Expected {actual!r} to have key {expected!r}",
    ),
    Operator(
        "not_has_key", Arity.BINARY,
        lambda actual, expected: not _has_key(actual, expected),
        "Expected {actual!r} to NOT have key {expected!r}",
    ),
    Operator(
        "gt", Arity.BINARY,
        _numeric(lambda left, right: left > right),
        "Expected {actual!r} to be greater than {expected!r}",
    ),
    Operator(
        "gte", Arity.BINARY,
        _numeric(lambda left, right: left >= right),
        "Expected {actual!r} to be greater than or equal to {expected!r}",
    ),
    Operator(
        "lt", Arity.BINARY,
        _numeric(lambda left, right: left < right),
        "Expected {actual!r} to be less than {expected!r}",
    ),
    Operator(
        "lte", Arity.BINARY,
        _numeric(lambda left, right: left <= right),
        "Expected {actual!r} to be less than or equal to {expected!r}",
    ),
    Operator(
        "length_equals", Arity.BINARY,
        _sized(lambda length, wanted: length == wanted),
        "Expected {actual!r} to have length {expected!r}",
    ),
    Operator(
        "length_gt", Arity.BINARY,
        _sized(lambda length, wanted: length > wanted),
        "Expected {actual!r} to be longer than {expected!r}",
    ),
    Operator(
        "length_lt", Arity.BINARY,
        _sized(lambda length, wanted: length < wanted),
        "Expected {actual!r} to be shorter than {expected!r}",
    ),
    Operator(
        "between", Arity.RANGE,
        _bounded(lambda value, low, high: low <= value <= high),
        "Expected {actual!r} to be between {expected[0]!r} and {expected[1]!r}",
    ),
)

_OPERATORS: dict[str, Operator] = {operator.name: operator for operator in _TABLE}

#: Operators that take no ``value``; giving one is meaningless, not an error.
UNARY_OPERATORS: frozenset[str] = frozenset(
    name for name, operator in _OPERATORS.items() if operator.arity is Arity.UNARY
)

#: Operators that read ``min``/``max`` instead of ``value``.
RANGE_OPERATORS: frozenset[str] = frozenset(
    name for name, operator in _OPERATORS.items() if operator.arity is Arity.RANGE
)


def arity_of(operator: str) -> Arity | None:
    """Which operands *operator* reads, or ``None`` if the name is unknown.

    The arity is already declared per operator in the table above; exposing it
    lets the vocabulary reject an assertion that supplies an operand the check
    will not read, instead of letting the operand be silently discarded.
    """
    known = _OPERATORS.get(operator)
    return known.arity if known is not None else None

# A name declared in the vocabulary but missing from the table would fail at
# runtime as "unknown", which is the confusing way to find out that the two
# halves of this module disagree.
assert frozenset(_OPERATORS) == OPERATORS, (
    f"operator vocabulary and table disagree: {OPERATORS ^ frozenset(_OPERATORS)}"
)


def apply_operator(operator: str, actual: object, expected: object) -> tuple[bool, str]:
    """Compare *actual* against *expected* under *operator*.

    Returns whether the comparison held and, when it did not, a message saying
    what was wanted and what arrived; a check that held carries no message. An
    operator outside :data:`OPERATORS`, and operands the operator cannot read,
    both fail loudly rather than quietly passing something else off as the check.
    """
    known = _OPERATORS.get(operator)
    if known is None:
        return False, (
            f"Unknown operator {operator!r}. Known operators: {', '.join(sorted(OPERATORS))}"
        )
    try:
        passed = bool(known.check(actual, expected))
    except OperandError as error:
        return False, str(error)
    return passed, "" if passed else known.message.format(actual=actual, expected=expected)

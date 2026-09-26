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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5, Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Operand shaping — turning a comparison's raw operands into what it reads.

Each adapter here takes one family of operands (numbers, counts, a range, a
set, text) and hands its comparison the arguments it actually wants, rejecting
the pairs that cannot be compared with :class:`OperandError`. The operator
table in :mod:`~tractusx_testlab.steps.assertions.operators` is built from them.
"""

from __future__ import annotations

import re
from collections.abc import Callable


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


def numeric(compare: Callable[[float, float], bool]) -> Check:
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


def sized(compare: Callable[[int, int], bool]) -> Check:
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


def bounded(compare: Callable[[float, float, float], bool]) -> Check:
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


def as_text(value: object) -> str:
    """Spell *value* the way a TCK writes it, so text compares against it.

    ``str(True)`` is Python's ``"True"``; the YAML a test is written in spells
    the same value ``true``. A step output that is a boolean is therefore read
    as ``true``/``false`` when it is compared with text — a check written as
    ``value: "true"`` means the boolean, and must not fail against it on the
    capital letter alone.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def same(actual: object, expected: object) -> bool:
    """Whether *actual* and *expected* are the same value, or the same text.

    Text is the fallback because an expectation often arrives as text for a
    value that is not: ``"200"`` for a status code, ``"true"`` for a flag. A
    boolean compared with text is matched regardless of case, since ``True``
    and ``TRUE`` are spellings of the one value, never a different one.
    """
    if actual == expected:
        return True
    left, right = as_text(actual), as_text(expected)
    if isinstance(actual, bool) or isinstance(expected, bool):
        return left.lower() == right.lower()
    return left == right


def is_member(actual: object, expected: object) -> bool:
    """Ask whether *actual* is in *expected*, a lone value standing for a set of one."""
    allowed = expected if isinstance(expected, (list, tuple, set)) else (expected,)
    try:
        return actual in allowed
    except TypeError as error:
        raise OperandError(f"Cannot look for {actual!r} inside {expected!r}") from error


def has_key(actual: object, expected: object) -> bool:
    """Ask whether *actual* is a mapping carrying the key *expected*."""
    if not isinstance(actual, dict):
        return False
    try:
        return expected in actual
    except TypeError as error:
        raise OperandError(f"{expected!r} cannot be used as a key") from error


def matches(actual: object, expected: object) -> bool:
    """Search *actual* for the pattern *expected*, which only text can satisfy."""
    if not isinstance(actual, str):
        return False
    try:
        return re.search(str(expected), actual) is not None
    except re.error as error:
        raise OperandError(f"{expected!r} is not a valid regular expression") from error

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

"""What a ``validate:`` entry's ``uses`` names, and what it needs to run.

``validate/*`` is the whole assertion vocabulary. A TCK either names the check
inline — ``validate/assert`` with an ``operator`` — or names it in the ``uses``
itself — ``validate/assert/equals``. Both spellings resolve here to the same
three pieces of information, so nothing downstream has to care which was used.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from tractusx_testlab.steps.assertions.operators import OPERATORS, Arity, arity_of

#: The operator assumed when a ``validate/assert`` block names none.
DEFAULT_OPERATOR = "not_null"


class AssertionKind(enum.Enum):
    """The three shapes a ``validate:`` entry comes in."""

    #: ``validate/assert`` — compare the value at ``input``.
    ASSERT = "assert"
    #: ``validate/field`` — compare the value at ``input``, then ``path`` within it.
    FIELD = "field"
    #: ``validate/schema`` — validate the value at ``input`` against a JSON Schema.
    SCHEMA = "schema"


_PREFIX_TO_KIND = {
    "validate/assert": AssertionKind.ASSERT,
    "validate/field": AssertionKind.FIELD,
    "validate/schema": AssertionKind.SCHEMA,
}


@dataclass(frozen=True)
class ResolvedAssertion:
    """A ``uses`` string understood: which check, and under which operator."""

    kind: AssertionKind
    #: ``None`` for :attr:`AssertionKind.SCHEMA`, which takes no operator.
    operator: str | None


def resolve(uses: str, params: dict) -> ResolvedAssertion | str:
    """Resolve *uses* into the check to run, or return why it cannot be.

    The operator comes from the ``uses`` suffix when it has one
    (``validate/assert/equals``) and from ``with.operator`` when it does not
    (``validate/assert`` + ``operator: equals``). Returning the reason instead
    of raising lets the caller report an unusable assertion as a failed one,
    which is what a test author needs to see.
    """
    kind = _PREFIX_TO_KIND.get(uses)
    if kind is not None:
        return _resolve_known_prefix(kind, params)

    prefix, _, suffix = uses.rpartition("/")
    kind = _PREFIX_TO_KIND.get(prefix)
    if kind is None or kind is AssertionKind.SCHEMA:
        return (
            f"Unknown assertion {uses!r}. Assertions are 'validate/assert', "
            f"'validate/field', 'validate/schema', or one of those with an "
            f"operator suffix such as 'validate/assert/equals'."
        )
    if suffix not in OPERATORS:
        return _unknown_operator(suffix, uses)
    return ResolvedAssertion(kind=kind, operator=suffix)


def _resolve_known_prefix(
    kind: AssertionKind, params: dict
) -> ResolvedAssertion | str:
    """Resolve the suffix-less spellings, which read their operator from ``with``."""
    if kind is AssertionKind.SCHEMA:
        return ResolvedAssertion(kind=kind, operator=None)
    operator = params.get("operator", DEFAULT_OPERATOR)
    if operator not in OPERATORS:
        return _unknown_operator(operator, None)
    return ResolvedAssertion(kind=kind, operator=operator)


#: Which ``with:`` keys each arity reads. Anything else the author supplied is
#: an operand the check will never look at.
_OPERANDS: dict[Arity, frozenset[str]] = {
    Arity.UNARY: frozenset(),
    Arity.BINARY: frozenset({"value"}),
    Arity.RANGE: frozenset({"min", "max"}),
}

#: Keys that are part of the block's grammar rather than operands.
_NON_OPERANDS = frozenset({"input", "path", "operator", "severity", "schema", "source"})


def check_operands(operator: str, params: dict) -> str | None:
    """Return why *params* cannot be what *operator* reads, or ``None`` if they can.

    The failure this prevents: ``validate/assert`` with a ``value:`` and no
    ``operator:`` resolves to the default ``not_null``, which reads no second
    operand at all. The ``value`` the author wrote is discarded, the check passes
    against anything non-null, and the YAML still reads like an equality test.

    Rejecting the mismatch is narrower than removing the default, and it is the
    part that is actually wrong: of the 22 bare assertions in the shipped TCKs,
    11 rely on the ``not_null`` default deliberately and none supply an operand
    it would ignore.
    """
    arity = arity_of(operator)
    if arity is None:
        return None  # unknown operator — already reported by the caller

    expected = _OPERANDS[arity]
    supplied = {key for key in params if key not in _NON_OPERANDS}

    ignored = supplied - expected
    if ignored:
        return (
            f"Operator '{operator}' does not read {', '.join(sorted(repr(i) for i in ignored))}. "
            + (
                f"It compares against {', '.join(sorted(expected))}."
                if expected
                else "It takes no comparison operand — did you mean to name an operator?"
            )
        )

    missing = expected - supplied
    if missing:
        return (
            f"Operator '{operator}' needs {', '.join(sorted(missing))}, which is not set."
        )
    return None


def _unknown_operator(operator: object, uses: str | None) -> str:
    """Say which operator was not understood, and name the ones that are."""
    where = f" in {uses!r}" if uses else ""
    return (
        f"Unknown operator {operator!r}{where}. "
        f"Known operators: {', '.join(sorted(OPERATORS))}"
    )

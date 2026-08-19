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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""What a catalog offers and what a policy demands, read as flat conditions.

A policy is a tree: rules under a permission or a prohibition, constraints under
each rule, and the real conditions under an ``and`` or an ``or`` inside those —
each level spelled two ways, because a DSP 2025-1 connector expands the terms a
legacy one prefixes.  Nothing that compares two policies wants to walk that
tree, and everything that reads one has to.

So the tree is read once, here, into the conditions at the bottom of it:
``leftOperand operator rightOperand``, each tagged with the rule it constrains.
The nesting is dropped deliberately.  ``and`` and ``or`` say how the conditions
combine, which is a question about what a policy *means*; which conditions are
there at all is the question a rejected offer raises, and the answer to that is
a set — which is why :mod:`~tractusx_testlab.steps.connector.policy_mismatch`
can answer it with one subtraction.

Reading, not judging: whether an offer is acceptable is the SDK's decision, and
nothing here compares anything.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, NamedTuple

from tractusx_testlab.steps.dsp_keys import (
    ASSET_ID_KEYS,
    CONSTRAINT_KEYS,
    DATASET_KEYS,
    ID_KEY,
    LEFT_OPERAND_KEYS,
    LOGICAL_KEYS,
    OPERATOR_KEYS,
    POLICY_KEYS,
    RIGHT_OPERAND_KEYS,
    RULE_KEYS,
    first_present,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

#: The rule kind so ordinary that naming it on every line would be noise.
_DEFAULT_RULE = "permission"


class Constraint(NamedTuple):
    """One atomic ODRL condition, as both sides of a comparison state it.

    ``rule`` is what the condition constrains — a permission, a prohibition or
    an obligation — and is part of the identity: the same condition permitting
    something and prohibiting it are opposite requirements, and treating them as
    equal would explain a mismatch by claiming there is none.
    """

    rule: str
    left: str
    operator: str
    right: str

    def __str__(self) -> str:
        return f"{self.left} {self.operator} {self.right}"

    def described(self) -> str:
        """The condition with its rule kind, for the kinds that are not the usual one.

        Nearly every policy in the wild constrains a permission, so saying so on
        every line is noise; a prohibition or an obligation is exactly the thing
        a reader must not skim past.
        """
        return str(self) if self.rule == _DEFAULT_RULE else f"{self.rule}: {self}"


class Offer(NamedTuple):
    """One policy a catalog makes an asset available under."""

    asset_id: str
    offer_id: str
    policy: Any


def constraints_of(policy: Any) -> tuple[Constraint, ...]:
    """Every atomic condition a policy imposes, whichever dialect wrote it."""
    if not isinstance(policy, dict):
        return ()
    found: list[Constraint] = []
    for rule, keys in RULE_KEYS.items():
        for entry in _as_list(first_present(policy, keys)):
            if isinstance(entry, dict):
                found.extend(_constraints_in(entry, rule))
    return tuple(found)


def offers_of(catalog: dict | None) -> list[Offer]:
    """The catalog's offers, in the order the provider made them.

    One asset is offered under as many policies as the provider wrote contract
    definitions for it, so an offer — not a dataset — is the unit that was
    accepted or rejected, and the unit a rejection has to account for.
    """
    if not isinstance(catalog, dict):
        return []
    offers: list[Offer] = []
    for dataset in _as_list(first_present(catalog, DATASET_KEYS)):
        if not isinstance(dataset, dict):
            continue
        asset_id = _as_text(first_present(dataset, ASSET_ID_KEYS))
        for policy in _as_list(first_present(dataset, POLICY_KEYS)):
            offers.append(Offer(asset_id, _as_text((policy or {}).get(ID_KEY)), policy))
    return offers


def _constraints_in(rule_body: dict, rule: str) -> Iterator[Constraint]:
    """The conditions of one rule, walking through whatever logic combines them."""
    for constraint in _as_list(first_present(rule_body, CONSTRAINT_KEYS)):
        yield from _atoms(constraint, rule)


def _atoms(constraint: Any, rule: str) -> Iterator[Constraint]:
    """The comparisons at the bottom of a constraint tree."""
    if not isinstance(constraint, dict):
        return
    nested = [item for key in LOGICAL_KEYS for item in _as_list(constraint.get(key))]
    if nested:
        for item in nested:
            yield from _atoms(item, rule)
        return
    left = first_present(constraint, LEFT_OPERAND_KEYS)
    if left is None:
        return
    yield Constraint(
        rule=rule,
        left=_as_text(left),
        operator=_as_text(first_present(constraint, OPERATOR_KEYS)),
        right=_as_text(first_present(constraint, RIGHT_OPERAND_KEYS)),
    )


def _as_list(value: Any) -> list[Any]:
    """A value that may be one thing or several, as several.

    A provider with a single offer sends a mapping where one with two sends a
    list, and both say the same thing.
    """
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _as_text(value: Any) -> str:
    """A JSON-LD value as the one string a comparison prints.

    Both dialects write a term either plainly or as a node reference
    (``{"@id": "odrl:eq"}``), and a right operand may be a list of accepted
    values. All of them are read and printed as they were written: a provider
    that spells ``cx-policy:Membership`` where the script wrote ``Membership``
    has stated a different condition, and quietly folding the two together would
    explain the mismatch away instead of naming it.
    """
    if isinstance(value, dict):
        return _as_text(value.get(ID_KEY, value))
    if isinstance(value, list):
        return ", ".join(_as_text(item) for item in value)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

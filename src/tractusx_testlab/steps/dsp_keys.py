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

"""The JSON-LD keys a DSP document is read under, in each dataspace generation.

The same catalog is spelled differently depending on which DSP generation wrote
it.  Legacy connectors (EDC 0.8-0.10, DSP HTTP 2024 — the ``jupiter`` release)
carry the namespace prefix in every key, so the offers arrive under
``dcat:dataset`` and their policies under ``odrl:hasPolicy``.  DSP 2025-1
connectors (EDC 0.11+ — the ``saturn`` release) set ``@vocab`` in the
``@context``, which expands every term, so the very same offers arrive under
``dataset`` and ``hasPolicy``.

The spellings are not restated here: they come from
:mod:`tractusx_sdk.dataspace.constants`, the component that speaks both
dialects.  A key the SDK renames must not need renaming here too.

A document is read under *every* spelling rather than under the one the run's
``dataspace_version`` implies, and in the same order the SDK's own ``DspTools``
tries them.  The run's version says which connector *we* drive; the catalog was
written by the counter-party's, which is free to be a generation behind.
"""

from __future__ import annotations

from typing import Any

from tractusx_sdk.dataspace.constants import (
    DCATKeys,
    DCATKeysDSP2025,
    JSONLDKeys,
    ODRLKeys,
    ODRLKeysDSP2025,
)

#: JSON-LD node identifier — the one key both generations spell the same way.
ID_KEY: str = JSONLDKeys.AT_ID

#: Where a catalog carries its dataset offers: DSP 2025-1 first, then legacy.
DATASET_KEYS: tuple[str, ...] = (DCATKeysDSP2025.DATASET, DCATKeys.DATASET)

#: Where a dataset carries the offers' ODRL policies.
POLICY_KEYS: tuple[str, ...] = (ODRLKeysDSP2025.POLICY, ODRLKeys.POLICY)

#: Where a dataset carries the id of the asset behind the offer.  The SDK names
#: no constant for this one: ``@vocab`` expands it to ``id`` and the prefixed
#: dialect writes ``edc:id``.  ``@id`` closes the list because a dataset whose
#: node identifier *is* the asset id carries neither property.
ASSET_ID_KEYS: tuple[str, ...] = ("id", "edc:id", ID_KEY)


def first_present(document: dict | None, keys: tuple[str, ...]) -> Any | None:
    """Return the value of the first of *keys* the document actually carries.

    "Carries" means present and not null: a key a provider sent as ``null`` is
    no more an answer than one it omitted, and the next spelling deserves a
    look before the caller is told there is nothing.
    """
    for key in keys:
        value = (document or {}).get(key)
        if value is not None:
            return value
    return None


#: Where a dataset carries the offers' ODRL policies, and where an offer carries
#: the rules those policies are made of.  Every rule kind is listed because a
#: policy is not only its permissions: a prohibition the provider adds is as
#: much a reason an offer was rejected as a permission it omits.
RULE_KEYS: dict[str, tuple[str, ...]] = {
    "permission": (ODRLKeysDSP2025.PERMISSION, ODRLKeys.PERMISSION),
    "prohibition": (ODRLKeysDSP2025.PROHIBITION, ODRLKeys.PROHIBITION),
    "obligation": (ODRLKeysDSP2025.OBLIGATION, ODRLKeys.OBLIGATION),
}

#: Where a rule carries its constraints.  The SDK names no constant for this
#: one: ``@vocab`` expands it to ``constraint`` and the prefixed dialect writes
#: ``odrl:constraint``.
CONSTRAINT_KEYS: tuple[str, ...] = ("constraint", "odrl:constraint")

#: Where a constraint carries further constraints instead of a comparison — the
#: ODRL logical operators.  Read in both dialects and both spellings, since a
#: policy nests its real conditions under one of them and the comparison this
#: module explains is against the atoms at the bottom.
LOGICAL_KEYS: tuple[str, ...] = (
    ODRLKeysDSP2025.ODRL_AND,
    ODRLKeys.ODRL_AND,
    ODRLKeysDSP2025.ODRL_OR,
    ODRLKeys.ODRL_OR,
)

#: The three parts of an atomic constraint, each in both dialects.
LEFT_OPERAND_KEYS: tuple[str, ...] = (ODRLKeysDSP2025.LEFT_OPERAND, ODRLKeys.LEFT_OPERAND)
OPERATOR_KEYS: tuple[str, ...] = (ODRLKeysDSP2025.OPERATOR, ODRLKeys.OPERATOR)
RIGHT_OPERAND_KEYS: tuple[str, ...] = (ODRLKeysDSP2025.RIGHT_OPERAND, ODRLKeys.RIGHT_OPERAND)

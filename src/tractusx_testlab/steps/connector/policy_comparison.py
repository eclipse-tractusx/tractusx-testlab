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

"""Every catalog offer measured against the policies a step expects.

The measure is the set of conditions (:mod:`~tractusx_testlab.steps.connector.policy_reading`):
what the provider requires that the expected policy does not carry, and what
the expected policy requires that the offer does not. When those agree the
reason is in the document around them — an action spelled another way,
conditions nested differently — and the SDK, which compared the documents, is
the one that can name it, so it is asked. Nothing here decides whether an
offer is acceptable: that was the SDK's call, and this reads a call it made.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from tractusx_sdk.dataspace.tools import DspTools

from tractusx_testlab.steps.connector.policy_reading import (
    Constraint,
    constraints_of,
    offers_of,
)


class OfferComparison(NamedTuple):
    """One catalog offer, measured against the expected policy closest to it."""

    asset_id: str
    offer_id: str
    offered: tuple[Constraint, ...]
    expected_index: int
    offered_not_expected: tuple[Constraint, ...]
    expected_not_offered: tuple[Constraint, ...]
    #: Beyond the conditions, in the SDK's words; read only when the conditions agree.
    other_differences: tuple[str, ...] = ()

    @property
    def differences(self) -> int:
        """How far this offer is from the expected policy it is closest to."""
        return len(self.offered_not_expected) + len(self.expected_not_offered)

    def as_context(self) -> dict[str, Any]:
        """The comparison as the trace carries it (ADR-0016 ``errors[].context``)."""
        return {
            "asset_id": self.asset_id,
            "offer_id": self.offer_id,
            "constraints": [item.described() for item in self.offered],
            "closest_expected_policy": self.expected_index,
            "offered_not_expected": [item.described() for item in self.offered_not_expected],
            "expected_not_offered": [item.described() for item in self.expected_not_offered],
            "other_differences": list(self.other_differences),
        }


def compare(catalog: dict | None, expected: list[Any]) -> list[OfferComparison]:
    """Measure every offer in the catalog against every expected policy.

    Each offer is reported against the expected policy it is *closest* to: a
    test naming three alternatives is not asking for three failures, it is
    asking which of them the provider came nearest to satisfying.
    """
    expectations = [constraints_of(policy) for policy in expected]
    if not expectations:
        # An empty allow-list rejects every offer without comparing anything, so
        # there is no comparison to report — only the empty list itself, which
        # the message names as the cause.
        return []
    comparisons = [
        (
            offer,
            _closest(offer.asset_id, offer.offer_id, constraints_of(offer.policy), expectations),
        )
        for offer in offers_of(catalog)
    ]
    return [
        item._replace(
            other_differences=document_differences(offer.policy, expected[item.expected_index])
        )
        if not item.differences
        else item
        for offer, item in comparisons
    ]


def _closest(
    asset_id: str,
    offer_id: str,
    offered: tuple[Constraint, ...],
    expectations: list[tuple[Constraint, ...]],
) -> OfferComparison:
    """The offer measured against whichever expected policy it differs from least."""
    candidates = [
        OfferComparison(
            asset_id=asset_id,
            offer_id=offer_id,
            offered=offered,
            expected_index=index,
            offered_not_expected=_ordered(offered, exclude=wanted),
            expected_not_offered=_ordered(wanted, exclude=offered),
        )
        for index, wanted in enumerate(expectations)
    ]
    return min(candidates, key=lambda item: item.differences)


def _ordered(
    items: tuple[Constraint, ...], exclude: tuple[Constraint, ...]
) -> tuple[Constraint, ...]:
    """The conditions in *items* that *exclude* does not carry, in their own order."""
    unwanted = set(exclude)
    return tuple(item for item in items if item not in unwanted)


def document_differences(offered: Any, expected: Any) -> tuple[str, ...]:
    """What the SDK finds different between two policies whose conditions agree.

    The SDK compares whole documents (rule keys, actions, how the conditions are
    nested), so when the conditions agree the reason is in that structure, and
    the SDK is the one that can name it. Its public ``evaluate_policy`` (0.9 and
    later) says it; an older SDK only has the helpers that wrote its DEBUG log.
    Nothing here decides anything: an SDK that offers neither leaves the
    explanation at "the same conditions", as before.
    """
    evaluate = getattr(DspTools, "evaluate_policy", None)
    if evaluate is not None:
        evaluation = evaluate(policy=offered, allowed_policies=[expected])
        return tuple(
            line
            for mismatch in getattr(evaluation, "mismatches", ())
            for line in (*mismatch.config_issues, *mismatch.differences)
        )
    try:
        from tractusx_sdk.dataspace.tools import dsp_tools  # older SDKs only
    except ImportError:
        return ()
    explain = getattr(dsp_tools, "_explain_policy_diff", None)
    normalize = getattr(dsp_tools, "_normalize_policy_value", None)
    if explain is None or normalize is None:
        return ()
    # What the SDK compares: from 0.8.5 the rules alone, so an offer's ``target``
    # is not named as a difference the SDK no longer counts.
    rules = getattr(dsp_tools, "_policy_rules", lambda policy: policy)
    return tuple(explain(normalize(rules(offered)), normalize(rules(expected))))

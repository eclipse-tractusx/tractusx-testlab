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

"""Why no offer in the catalog was accepted, in the terms the script was written in.

The SDK decides whether an offer's policy is acceptable, and when none is it
says so with a verdict: *no valid policy was found for any item in the list*.
That sentence is true and unusable — it names neither the offers the provider
made nor the condition that separated them from the policy the script asked for,
leaving the reader to diff two JSON-LD trees by eye, in a document they first
have to go and fetch.

The comparison is **not** repeated here. The SDK matches; this module explains a
match that already failed, from the catalog the SDK compared, which it now hands
over on the error itself. Both sides are read down to their atomic conditions
(:mod:`~tractusx_testlab.steps.connector.policy_reading`) and the difference is
reported as a set: what the provider requires that the expected policy does not
carry, and what the expected policy requires that the offer does not.

That difference is what the flat message hid. An offer is accepted only when its
policy matches an expected one in full, so a condition the provider *adds*
rejects it exactly as one it omits does — and a provider offering
``FrameworkAgreement`` **and** ``Membership`` **and** ``UsagePurpose`` to a
script expecting the first and the third is the common case. It now reads as one
line naming ``Membership``, in the console and, structurally, under the step
error's ``context`` (ADR-0016) for the IDE to render.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, NamedTuple

from tractusx_sdk.dataspace.tools import PolicyMismatchError as SdkPolicyMismatchError

from tractusx_testlab.models import ExecutionError
from tractusx_testlab.steps.connector.policy_reading import (
    Constraint,
    constraints_of,
    offers_of,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Offers spelled out in the message before the rest are left to the trace. A
#: catalog can carry dozens of near-identical offers and the first few say what
#: all of them say; the count of what was compared is stated either way, so the
#: reader is never shown a subset as if it were the whole.
_OFFERS_IN_MESSAGE = 3

#: Offers kept in the structured context. More than the message spells out — a
#: tool reading the trace can afford them — and still bounded, because the
#: catalog they came from is already in the trace in full.
_OFFERS_IN_CONTEXT = 20

#: Longest identifier printed whole. An EDC offer id is three base64 segments
#: and runs past 100 characters, which buries the line it appears on; the full
#: value stays in the structured context.
_ID_CHARS = 24


class OfferComparison(NamedTuple):
    """One catalog offer, measured against the expected policy closest to it."""

    asset_id: str
    offer_id: str
    offered: tuple[Constraint, ...]
    expected_index: int
    offered_not_expected: tuple[Constraint, ...]
    expected_not_offered: tuple[Constraint, ...]

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
        }


class PolicyMismatchError(ExecutionError):
    """No offer in the catalog is made under a policy the step accepts.

    A result about the counter-party, not a fault of the engine: the provider
    published offers, the engine read them, and they are not the ones the TCK
    requires. Which of the two is wrong — the deployment or the policy the
    script expects — is the reader's call, and the comparison is what lets them
    make it.
    """

    code = "POLICY_MISMATCH"

    def __init__(self, message: str, diagnostics: dict[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


@contextmanager
def explained(counter_party_address: str) -> Iterator[None]:
    """Run a DSP flow, and replace its policy verdict with the comparison behind it.

    Only that one failure is touched. Anything else the flow raises — a refused
    connection, a negotiation that never finalised, a transfer that timed out —
    passes through unchanged, because none of them is about the policy and
    dressing them in a policy explanation would be worse than the flat message.
    """
    try:
        yield
    except RuntimeError as exc:
        mismatch = _explain(exc, counter_party_address)
        if mismatch is None:
            raise
        raise mismatch from exc


def compare(catalog: dict | None, expected: list[Any]) -> list[OfferComparison]:
    """Measure every offer in the catalog against every expected policy.

    Each offer is reported against the expected policy it is *closest* to: a
    script naming three alternatives is not asking for three failures, it is
    asking which of them the provider came nearest to satisfying.
    """
    expectations = [constraints_of(policy) for policy in expected]
    if not expectations:
        # An empty allow-list rejects every offer without comparing anything, so
        # there is no comparison to report — only the empty list itself, which
        # the message names as the cause.
        return []
    return [
        _closest(offer.asset_id, offer.offer_id, constraints_of(offer.policy), expectations)
        for offer in offers_of(catalog)
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


def _explain(exc: RuntimeError, counter_party_address: str) -> PolicyMismatchError | None:
    """The comparison behind a flow failure, or ``None`` when it was not about policy.

    The evidence is read off the cause the SDK chains to its own message: the
    catalog it compared and the allow-list it compared it against. Nothing is
    fetched and nothing is guessed — a failure carrying no such cause is a
    different failure, and is left to speak for itself.
    """
    cause = exc.__cause__
    if not isinstance(cause, SdkPolicyMismatchError):
        return None
    expected = cause.allowed_policies
    if expected is None:
        # "Accept anything" cannot produce a policy mismatch. If it somehow did,
        # this module has nothing to add and the SDK's message stands.
        return None
    comparisons = compare(cause.catalog, expected)
    if not comparisons and expected:
        # Nothing was read out of the catalog to compare: the failure is that the
        # provider published no offer at all, which its own message says.
        return None
    return PolicyMismatchError(
        _message(comparisons, expected, counter_party_address),
        _diagnostics(comparisons, expected, counter_party_address),
    )


def _message(
    comparisons: list[OfferComparison],
    expected: list[Any],
    counter_party_address: str,
) -> str:
    """The comparison as a person reads it, in the console and the transcript."""
    lines = [f"no offer from {counter_party_address} is made under a policy this step accepts"]
    if not expected:
        lines.append(
            "  'expected_policies' is an empty list, which accepts no offer at all. "
            "Name the policies an offer may carry, or omit the key to take any offer."
        )
        return "\n".join(lines)

    plural = "" if len(comparisons) == 1 else "s"
    lines.append(f"  {len(comparisons)} offer{plural} compared, none matched:")
    for comparison in comparisons[:_OFFERS_IN_MESSAGE]:
        lines.extend(_offer_lines(comparison, several=len(expected) > 1))
    if len(comparisons) > _OFFERS_IN_MESSAGE:
        lines.append(
            f"    ... and {len(comparisons) - _OFFERS_IN_MESSAGE} further offer(s), in the trace"
        )
    for index, wanted in enumerate(expected):
        label = f"  expected policy [{index}]" if len(expected) > 1 else "  expected"
        lines.append(f"{label}: {_listed(constraints_of(wanted)) or 'no conditions at all'}")
    lines.append(
        "  An offer is accepted only when its policy matches an expected one in full, "
        "so a condition the provider adds rejects it just as one it omits does."
    )
    return "\n".join(lines)


def _offer_lines(comparison: OfferComparison, several: bool) -> list[str]:
    """One offer's difference from the expected policy it came closest to."""
    against = f" against expected policy [{comparison.expected_index}]" if several else ""
    lines = [
        f"    offer {_short(comparison.offer_id)} on asset {_short(comparison.asset_id)}{against}:"
    ]
    if comparison.offered_not_expected:
        lines.append(
            f"      the provider also requires: {_listed(comparison.offered_not_expected)}"
        )
    if comparison.expected_not_offered:
        lines.append(
            f"      the provider does not offer: {_listed(comparison.expected_not_offered)}"
        )
    if not comparison.differences:
        lines.append(
            "      the same conditions on both sides — the offer differs elsewhere in "
            "the policy document (compare it in the trace)"
        )
    return lines


def _diagnostics(
    comparisons: list[OfferComparison],
    expected: list[Any],
    counter_party_address: str,
) -> dict[str, Any]:
    """The comparison as a tool reads it, under the step error's ``context``."""
    return {
        "counter_party_address": counter_party_address,
        "offers_compared": len(comparisons),
        "expected_policies": [
            [item.described() for item in constraints_of(policy)] for policy in expected
        ],
        "offers": [item.as_context() for item in comparisons[:_OFFERS_IN_CONTEXT]],
    }


def _listed(constraints: tuple[Constraint, ...]) -> str:
    """Conditions on one line, quoted so an empty operand is still visible."""
    return ", ".join(f"'{item.described()}'" for item in constraints)


def _short(value: str) -> str:
    """An identifier at a length that leaves the line readable."""
    if len(value) <= _ID_CHARS:
        return f"'{value}'"
    return f"'{value[:_ID_CHARS]}…'"

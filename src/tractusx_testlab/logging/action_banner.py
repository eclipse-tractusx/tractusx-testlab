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

"""The box the console draws when a run stops and waits for the system under test.

Every other line of a run scrolls by; this is the one moment a person may have
to act, by hand, before a timeout fails the test. One log line among hundreds
is easy to miss, so the wait is framed — ``=`` above and below, ``ACTION
REQUIRED`` and the time it waits in the first row — and says, in order, what to
do: the test's own ``action`` when it declared one, else what the listener
implies (call this URL; or find this offer, negotiate it, call through the data
plane). Plain ASCII, so it survives every terminal and CI log.
"""

from __future__ import annotations

_WIDTH = 78
_RULE = "=" * _WIDTH
_THIN = "-" * _WIDTH


def _literal(value: object) -> str:
    """A property value as text: ``{"@id": …}`` reads as its IRI."""
    if isinstance(value, dict) and value.get("@id"):
        return str(value["@id"])
    return str(value)


def _offer_rows(offer: dict) -> list[str]:
    rows = ["  Find the offer in the catalog of the test suite's connector:"]
    if offer.get("dsp_url"):
        rows.append(f"    connector  {offer['dsp_url']}")
    if offer.get("participant_id"):
        rows.append(f"    id         {offer['participant_id']}")
    filters = offer.get("catalog_filters") or [
        {
            "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
            "operator": "=",
            "operandRight": offer.get("asset_id", "?"),
        }
    ]
    for index, criterion in enumerate(filters):
        label = "filter" if index == 0 else ""
        rows.append(
            f"    {label:<10} {criterion.get('operandLeft')} {criterion.get('operator', '=')} "
            f"{criterion.get('operandRight')}"
        )
    return rows


def _default_steps(listener: dict) -> list[str]:
    method, path = listener.get("method", "?"), listener.get("path", "?")
    if listener.get("via") == "dataplane":
        return [
            "Request the catalog of the connector above, with the filter above.",
            "Negotiate the offer it returns and get its EDR.",
            f"Send {method} {path} to the EDR's data plane endpoint, "
            "with the EDR token as Authorization.",
        ]
    return [f"Send {method} {listener.get('url', '?')}."]


def action_banner(data: dict) -> str:
    """The framed block for a ``step_waiting`` event: what to do, and by when."""
    listener = data.get("listener") or {}
    action = listener.get("action") or {}
    timeout = data.get("timeout_s")
    title = f"ACTION REQUIRED — {action['label']}" if action.get("label") else "ACTION REQUIRED"
    budget = f"waits up to {float(timeout):.0f}s" if timeout else ""
    pad = max(1, _WIDTH - 2 - len(title) - len(budget))
    rows = [_RULE, f"  {title}{' ' * pad}{budget}".rstrip()]
    where = f"[{data.get('test_id', '')}] {data.get('step_id') or ''}".rstrip()
    rows += [f"  {where}", _THIN]
    if action.get("description"):
        rows += [f"  {action['description']}", ""]
    offer = listener.get("offer")
    if listener.get("via") == "dataplane" and isinstance(offer, dict):
        rows += [*_offer_rows(offer), ""]
    steps = action.get("recommendation") or _default_steps(listener)
    rows.append("  What to do:")
    rows += [f"    {number}. {step}" for number, step in enumerate(steps, start=1)]
    fields = action.get("fields") or []
    if fields:
        rows += ["", "  Values:"]
        width = max(len(str(field.get("label", ""))) for field in fields)
        rows += [
            f"    {field.get('label', '')!s:<{width}}  {_literal(field.get('value'))}"
            for field in fields
        ]
    rows.append(_RULE)
    return "\n".join(rows)

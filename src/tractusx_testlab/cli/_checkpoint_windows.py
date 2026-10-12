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

"""The two windows ``testlab run`` draws for a person: the briefing, and a choice (ADR-0028).

The briefing comes before anything runs: every checkpoint the run will ask for,
grouped by test, each with what it asks of whom::

    ==========================================================================
      THIS RUN NEEDS YOU AT 2 CHECKPOINTS
    --------------------------------------------------------------------------
      Push the certificate
          1  await_push   inbound · your system calls us
             1m 00s to answer · Push the certificate to the Test Suite
      Choose the offer
          2  pick_offer   internal · you choose
             5m 00s to answer · may repeat · Pick the offer to negotiate
    ==========================================================================
    Continue? [y/N]:

A choice is one window per question, its options numbered. Both are lines of
text: the caller prints them, and the transcript gets them as printed.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from tractusx_testlab.logging.window import fit, terminal_width, window, wrapped
from tractusx_testlab.models.primitives.checkpoint import Direction
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry
from tractusx_testlab.models.runtime.selection import SelectionOption
from tractusx_testlab.player.operator import Question

#: What each direction asks, in the fewest words.
SHORT_MEANINGS: dict[Direction, str] = {
    Direction.INBOUND: "your system calls us",
    Direction.OUTBOUND: "we call your system",
    Direction.INTERNAL: "you choose",
}


def briefing(checkpoints: Sequence[CheckpointEntry], width: int | None = None) -> list[str]:
    """The window listing *checkpoints*, numbered in run order and grouped by test.

    Each checkpoint is a row with its number, its step, its direction and what
    that asks, then, wrapped beneath, its timeout, its flags and what the test
    calls it — wrapped rather than cut, so nothing of it is lost.
    """
    count = len(checkpoints)
    title = f"THIS RUN NEEDS YOU AT {count} CHECKPOINT{'S' if count != 1 else ''}"
    text_width = width_of(width)
    step_width = max(len(_step(entry)) for entry in checkpoints)
    body: list[str] = []
    test = None
    for number, entry in enumerate(checkpoints, start=1):
        if entry.test_id != test:
            test = entry.test_id
            body.append(f"  {entry.test_name or entry.test_id}")
        direction = f"{entry.direction} · {SHORT_MEANINGS[entry.direction]}"
        body.append(f"  {number:>3}  {_step(entry):<{step_width}}   {direction}")
        about = " · ".join(_about(entry))
        if about:
            body += wrapped(about, text_width, indent=" " * 7)
    return window(title, body, width=text_width)


def choice(question: Question, remaining_s: float, width: int | None = None) -> list[str]:
    """The window putting *question* to the operator, its options numbered from 1."""
    where = f"CHECKPOINT {question.number} of {question.total} · " if question.number else ""
    entry, action = question.entry, question.selection.action
    label = (action.label if action else None) or (entry.label if entry else None)
    description = (action.description if action else None) or (entry.description if entry else None)
    text_width = width_of(width)
    body = [*wrapped(label or _step_of(question), text_width)]
    if description:
        body += wrapped(description, text_width)
    body.append("")
    options = question.selection.options
    body += [_option_row(n, option) for n, option in enumerate(options, start=1)]
    return window(f"{where}YOU CHOOSE", body, aside=f"{clock(remaining_s)} left", width=text_width)


def width_of(width: int | None) -> int:
    """*width*, else the terminal's (``logging.window.terminal_width``)."""
    return width or terminal_width()


def clock(seconds: float) -> str:
    """``4m 52s``, ``52s``: how long is left, to the second."""
    whole = max(0, int(seconds))
    minutes, rest = divmod(whole, 60)
    return f"{minutes}m {rest:02d}s" if minutes else f"{rest}s"


def _about(entry: CheckpointEntry) -> list[str]:
    """The timeout, the flags and the label of *entry*, those it has."""
    text = entry.label or entry.description or entry.name
    return [
        *([f"{clock(entry.timeout_s)} to answer"] if entry.timeout_s else []),
        *(["only on some paths"] if entry.conditional else []),
        *(["may repeat"] if entry.repeated else []),
        *([text] if text else []),
    ]


def _step(entry: CheckpointEntry) -> str:
    return entry.step_id or entry.uses


def _step_of(question: Question) -> str:
    return question.step_id or "Choose one option"


def _option_row(number: int, option: SelectionOption) -> str:
    """``  3  label · description · asset … · policy · offer …``, as much as the details say.

    The policy before the offer id: which conditions an offer sets is what tells
    two offers of one asset apart, its id is what a person copies.
    """
    details = option.details or {}
    parts = [option.label]
    if option.description and option.description != option.label:
        parts.append(option.description)
    if details.get("asset_id") and str(details["asset_id"]) != option.label:
        parts.append(f"asset {fit(str(details['asset_id']), 14)}")
    policy = policy_summary(details.get("policy"))
    if policy:
        parts.append(policy)
    offer = details.get("offer_id")
    if offer and str(offer) not in (option.description or ""):
        parts.append(f"offer {fit(str(offer), 14)}")
    return f"    {number:>2}  " + " · ".join(parts)


def policy_summary(policy: Any) -> str:
    """The conditions an ODRL offer sets, by name: ``Membership, FrameworkAgreement``."""
    names = list(dict.fromkeys(_left_operands(policy)))
    return ", ".join(names)


def _left_operands(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key.split(":")[-1].split("/")[-1] == "leftOperand":
                operand = value.get("@id") if isinstance(value, dict) else value
                if operand:
                    yield str(operand).replace("#", "/").replace(":", "/").split("/")[-1]
            else:
                yield from _left_operands(value)
    elif isinstance(node, list):
        for item in node:
            yield from _left_operands(item)

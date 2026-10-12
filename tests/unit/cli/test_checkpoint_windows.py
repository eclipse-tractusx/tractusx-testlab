################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The windows ``testlab run`` frames its briefing and its choices in (ADR-0028).

Snapshots at the narrowest and the widest a window is drawn: whatever is long
is wrapped (the briefing) or cut with an ellipsis (an option row), and the
frame is never broken.
"""

from __future__ import annotations

import pytest
import typer
from typer.testing import CliRunner

from tractusx_testlab.cli._checkpoint_windows import briefing, choice, clock, policy_summary
from tractusx_testlab.logging.window import MAX_WIDTH, MIN_WIDTH, fit, window
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry
from tractusx_testlab.models.runtime.selection import Selection, SelectionOption
from tractusx_testlab.player.operator import Question

_PUSH = CheckpointEntry(
    test_id="push",
    test_name="Push the certificate",
    phase="execution",
    position="execution/1",
    step_id="await_push",
    uses="mock/wait/http_request",
    direction="inbound",
    kind="wait",
    via="direct",
    label="Push the certificate to the Test Suite",
    timeout_s=60,
)
_OFFER = CheckpointEntry(
    test_id="offer",
    test_name="Choose the offer",
    phase="execution",
    position="execution/0/steps/0",
    step_id="pick_offer",
    uses="connector/datasets/select",
    direction="internal",
    kind="select",
    label="Pick the offer to negotiate",
    timeout_s=300,
    conditional=True,
    repeated=True,
)


def _constraint(*operands: str) -> dict:
    return {
        "odrl:permission": {
            "odrl:constraint": {"odrl:and": [{"odrl:leftOperand": {"@id": o}} for o in operands]}
        }
    }


_QUESTION = Question(
    job_id="job",
    step_id="pick_offer",
    selection=Selection(
        presentation="catalog_offers",
        options=[
            SelectionOption(
                id="a",
                label="CCMAPI notification 3.0",
                details={
                    "asset_id": "urn:uuid:7f3c1d2e-aaaa",
                    "offer_id": "b2ZmZXI6MQ==",
                    "policy": _constraint("cx-policy:Membership", "cx-policy:FrameworkAgreement"),
                },
            ),
            SelectionOption(
                id="b",
                label="CCMAPI notification 3.0",
                details={
                    "asset_id": "urn:uuid:a91e0000-bbbb",
                    "policy": _constraint("cx-policy:Membership"),
                },
            ),
        ],
    ),
    timeout_s=300,
    number=2,
    total=13,
    entry=_OFFER,
)


class TestTheBriefing:
    def test_at_60_columns(self) -> None:
        assert briefing([_PUSH, _OFFER], 60) == [
            "=" * 60,
            "  THIS RUN NEEDS YOU AT 2 CHECKPOINTS",
            "-" * 60,
            "  Push the certificate",
            "    1  await_push   inbound · your system calls us",
            "       1m 00s to answer · Push the certificate to the Test",
            "       Suite",
            "  Choose the offer",
            "    2  pick_offer   internal · you choose",
            "       5m 00s to answer · only on some paths · may repeat ·",
            "       Pick the offer to negotiate",
            "=" * 60,
        ]

    def test_at_100_columns(self) -> None:
        assert briefing([_PUSH, _OFFER], 100) == [
            "=" * 100,
            "  THIS RUN NEEDS YOU AT 2 CHECKPOINTS",
            "-" * 100,
            "  Push the certificate",
            "    1  await_push   inbound · your system calls us",
            "       1m 00s to answer · Push the certificate to the Test Suite",
            "  Choose the offer",
            "    2  pick_offer   internal · you choose",
            "       5m 00s to answer · only on some paths · may repeat · Pick the offer to negotiate",
            "=" * 100,
        ]

    def test_one_checkpoint_is_one(self) -> None:
        assert briefing([_PUSH], 80)[1] == "  THIS RUN NEEDS YOU AT 1 CHECKPOINT"

    def test_a_long_label_is_wrapped_and_never_breaks_the_frame(self) -> None:
        long = _PUSH.model_copy(update={"label": "word " * 60})
        lines = briefing([long], 60)
        assert max(len(line) for line in lines) == 60
        assert sum("word" in line for line in lines) > 3


class TestAChoice:
    def test_at_60_columns(self) -> None:
        assert choice(_QUESTION, 292, 60) == [
            "=" * 60,
            "  CHECKPOINT 2 of 13 · YOU CHOOSE                4m 52s left",
            "-" * 60,
            "  Pick the offer to negotiate",
            "",
            "     1  CCMAPI notification 3.0 · asset urn:uuid:7f3c… · Me…",
            "     2  CCMAPI notification 3.0 · asset urn:uuid:a91e… · Me…",
            "=" * 60,
        ]

    def test_at_100_columns(self) -> None:
        assert choice(_QUESTION, 292, 100)[5:7] == [
            "     1  CCMAPI notification 3.0 · asset urn:uuid:7f3c… · Membership, FrameworkAgreement"
            " · offer b2Z…",
            "     2  CCMAPI notification 3.0 · asset urn:uuid:a91e… · Membership",
        ]

    def test_a_long_title_and_option_are_cut_with_an_ellipsis(self) -> None:
        option = SelectionOption(id="x", label="x" * 300)
        question = Question(
            job_id="j",
            step_id="s",
            selection=Selection(options=[option]),
            timeout_s=5,
            number=1,
            total=1,
            entry=_OFFER.model_copy(update={"label": "y" * 300}),
        )
        lines = choice(question, 5, 60)
        assert all(len(line) <= 60 for line in lines)
        assert lines[-2].endswith("…")


def test_the_width_is_clamped_to_what_a_window_is_drawn_at(monkeypatch) -> None:
    import os

    from tractusx_testlab.logging import window as window_module

    for columns, expected in ((40, MIN_WIDTH), (80, 80), (240, MAX_WIDTH)):
        monkeypatch.setattr(
            window_module.shutil,
            "get_terminal_size",
            lambda *_, c=columns: os.terminal_size((c, 24)),
        )
        assert len(window("t")[0]) == expected


def test_a_cut_row_ends_in_an_ellipsis() -> None:
    assert fit("abcdef", 4) == "abc…" and fit("abc", 4) == "abc"


@pytest.mark.parametrize(("seconds", "text"), [(292, "4m 52s"), (52, "52s"), (-3, "0s")])
def test_the_clock(seconds: float, text: str) -> None:
    assert clock(seconds) == text


def test_a_policy_is_summarised_by_the_conditions_it_sets() -> None:
    assert policy_summary(_constraint("cx-policy:Membership", "https://w3id.org/x#Purpose")) == (
        "Membership, Purpose"
    )
    assert policy_summary(None) == ""


def test_no_colour_reaches_a_terminal_that_said_no_color(monkeypatch) -> None:
    """The windows are plain text; the title row is bold only where colour is wanted."""
    from tractusx_testlab.cli._terminal_operator import TerminalOperator

    app = typer.Typer()

    @app.command()
    def show() -> None:
        TerminalOperator(assume_yes=True, colour=False).approve([_PUSH])

    output = CliRunner().invoke(app, [], color=True).output
    assert "\x1b[" not in output
    assert "THIS RUN NEEDS YOU AT 1 CHECKPOINT" in output

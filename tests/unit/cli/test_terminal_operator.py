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

"""The person at the terminal: approving a run, answering its choices (ADR-0028).

The operator reads its input through a function, so what a person types, and
when, is scripted here: no terminal, no waiting.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from tractusx_testlab.cli._terminal_operator import TerminalOperator, parse_choices
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry
from tractusx_testlab.models.runtime.selection import Selection, SelectionOption
from tractusx_testlab.player.operator import Question, RunAborted

_ENTRY = CheckpointEntry(
    test_id="t",
    test_name="t",
    phase="execution",
    position="execution/0",
    step_id="pick",
    uses="flow/select",
    direction="internal",
    kind="select",
    label="Pick one",
    timeout_s=60,
)
_QUESTION = Question(
    job_id="job",
    step_id="pick",
    selection=Selection(
        options=[
            SelectionOption(id="alpha", label="Alpha"),
            SelectionOption(id="beta", label="Beta"),
        ]
    ),
    timeout_s=60,
    number=1,
    total=1,
    entry=_ENTRY,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _operator(
    lines: Iterable[str | None] = (), *, terminal: bool = True, clock: _Clock | None = None, **kw
) -> tuple[TerminalOperator, list[float | None]]:
    """An operator reading *lines* in turn; ``None`` is the time running out."""
    script, asked = iter(lines), []
    clock = clock or _Clock()

    def read(timeout: float | None) -> str | None:
        asked.append(timeout)
        line = next(script, "")
        if line is None and timeout is not None:
            clock.now += timeout
        return line

    operator = TerminalOperator(
        read_line=read, is_terminal=lambda: terminal, colour=False, width=60, now=clock, **kw
    )
    return operator, asked


class TestTheApproval:
    @pytest.mark.parametrize("answer", ["y\n", "Y\n", "yes\n"])
    def test_yes_approves(self, answer: str, capsys) -> None:
        operator, _ = _operator([answer])
        assert operator.approve([_ENTRY]) is True
        out = capsys.readouterr().out
        assert "THIS RUN NEEDS YOU AT 1 CHECKPOINT" in out
        assert "Continue? [y/N]: " in out and "Approved." in out

    @pytest.mark.parametrize("answer", ["n\n", "\n", "maybe\n", ""])
    def test_anything_else_declines(self, answer: str, capsys) -> None:
        operator, _ = _operator([answer])
        assert operator.approve([_ENTRY]) is False
        assert "Not approved: no test runs." in capsys.readouterr().out

    def test_yes_up_front_skips_the_question(self, capsys) -> None:
        operator, asked = _operator(terminal=False, assume_yes=True)
        assert operator.approve([_ENTRY]) is True
        assert asked == []
        assert "Continue? [y/N]: yes (--yes)" in capsys.readouterr().out

    def test_without_a_terminal_it_says_to_pass_yes_instead_of_hanging(self) -> None:
        operator, asked = _operator(terminal=False)
        with pytest.raises(RunAborted, match="--yes") as stopped:
            operator.approve([_ENTRY])
        assert stopped.value.reason == "no_answer" and asked == []


class TestAChoice:
    def test_a_number_chooses_its_option(self, capsys) -> None:
        operator, _ = _operator(["2\n"])
        assert operator.choose(_QUESTION) == "beta"
        out = capsys.readouterr().out
        assert "CHECKPOINT 1 of 1 · YOU CHOOSE" in out
        assert "Choose [1-2] (1m 00s left, q to stop): " in out and "Chosen: 2 Beta" in out

    @pytest.mark.parametrize("wrong", ["7\n", "beta\n", "\n"])
    def test_anything_else_asks_again_with_a_hint(self, wrong: str, capsys) -> None:
        operator, asked = _operator([wrong, "1\n"])
        assert operator.choose(_QUESTION) == "alpha"
        assert len(asked) == 2
        assert "Type a number from 1 to 2, or q to stop." in capsys.readouterr().out

    def test_q_stops_the_run(self) -> None:
        operator, _ = _operator(["q\n"])
        with pytest.raises(RunAborted, match="Stopped by the operator") as stopped:
            operator.choose(_QUESTION)
        assert stopped.value.reason == "quit"

    def test_it_waits_no_longer_than_the_step_does(self, capsys) -> None:
        clock = _Clock()
        operator, asked = _operator(["9\n", None], clock=clock)
        assert operator.choose(_QUESTION) is None
        assert asked == [60.0, 60.0]
        assert "No choice in time: checkpoint 1 (pick) times out." in capsys.readouterr().out

    def test_an_answer_given_up_front_is_taken_by_number_or_by_id(self) -> None:
        by_number, asked = _operator(terminal=False, choices={"pick": "2"})
        by_id, _ = _operator(terminal=False, choices={"pick": "alpha"})
        assert (by_number.choose(_QUESTION), by_id.choose(_QUESTION)) == ("beta", "alpha")
        assert asked == []

    def test_an_answer_up_front_that_names_no_option_stops_the_run(self) -> None:
        operator, _ = _operator(choices={"pick": "9"})
        with pytest.raises(RunAborted, match="names no option"):
            operator.choose(_QUESTION)

    def test_without_a_terminal_it_names_the_flag_instead_of_hanging(self) -> None:
        operator, _ = _operator(terminal=False)
        with pytest.raises(RunAborted, match="--choose pick=<1-2|option id>") as stopped:
            operator.choose(_QUESTION)
        assert stopped.value.reason == "no_answer"

    def test_yes_never_picks_an_option(self) -> None:
        operator, _ = _operator(terminal=False, assume_yes=True)
        with pytest.raises(RunAborted):
            operator.choose(_QUESTION)

    def test_the_end_of_the_input_stops_the_run(self) -> None:
        operator, _ = _operator([""])
        with pytest.raises(RunAborted, match="input ended"):
            operator.choose(_QUESTION)


def test_choose_entries_are_read_by_step_id() -> None:
    assert parse_choices(["pick=2", "offer = asset::1"]) == {"pick": "2", "offer": "asset::1"}
    with pytest.raises(Exception, match="step_id"):
        parse_choices(["pick"])

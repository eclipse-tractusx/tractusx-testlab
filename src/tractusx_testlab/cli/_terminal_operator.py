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

"""The person at the terminal, as the run's operator (``player.operator``, ADR-0028).

``testlab run`` shows the briefing before anything starts and asks
``Continue? [y/N]``; every choice the run puts to the operator is a window with
numbered options and ``Choose [1-N]``. Both are answered at the terminal, or up
front: ``--yes`` approves the briefing (it never picks an option), and
``--choose <step_id>=<n|option id>`` answers a choice. Without a terminal and
without an answer given up front, nothing hangs: the run stops, naming the flag.

Everything shown goes to stdout, so the transcript keeps it; what the person
typed is written after it (``Approved.``, ``Chosen: 2 beta``), since a terminal
echoes input itself and the transcript would otherwise not have it.
"""

from __future__ import annotations

import contextlib
import select
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager

import typer

from tractusx_testlab.cli._checkpoint_windows import briefing, choice, clock
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry
from tractusx_testlab.models.runtime.selection import SelectionOption
from tractusx_testlab.player.operator import Question, RunAborted

#: Reads one line, waiting at most the seconds given (``None``: as long as it
#: takes); ``None`` when the time ran out, ``""`` at the end of the input.
LineReader = Callable[[float | None], str | None]


def read_stdin(timeout: float | None) -> str | None:
    """A line from stdin, or ``None`` once *timeout* seconds passed without one."""
    if timeout is not None:
        try:
            ready, _, _ = select.select([sys.stdin], [], [], max(timeout, 0.0))
        except (OSError, ValueError):  # not a selectable stream: read as it comes
            ready = [sys.stdin]
        if not ready:
            return None
    return sys.stdin.readline()


class TerminalOperator:
    """Approves a run and answers its choices at the terminal (``player.operator.Operator``)."""

    def __init__(
        self,
        *,
        assume_yes: bool = False,
        choices: dict[str, str] | None = None,
        read_line: LineReader = read_stdin,
        is_terminal: Callable[[], bool] = lambda: sys.stdin.isatty(),
        colour: bool | None = None,
        width: int | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._assume_yes = assume_yes
        self._choices = dict(choices or {})
        self._read_line = read_line
        self._is_terminal = is_terminal
        self._colour = colour
        self._width = width
        self._now = now
        #: Stops whatever else draws on the terminal while a window is up.
        self.pause: Callable[[], AbstractContextManager[None]] = contextlib.nullcontext

    def approve(self, checkpoints: Sequence[CheckpointEntry]) -> bool:
        with self.pause():
            self._show(briefing(checkpoints, self._width))
            if self._assume_yes:
                self._say("Continue? [y/N]: yes (--yes)")
                return True
            if not self._is_terminal():
                raise RunAborted(
                    "There is no terminal to approve the checkpoints at: pass --yes "
                    "(or set TESTLAB_YES=1) to run without asking.",
                    "no_answer",
                )
            self._say("Continue? [y/N]: ", newline=False)
            answer = (self._read_line(None) or "").strip().lower()
            approved = answer in ("y", "yes")
            self._say("Approved." if approved else "Not approved: no test runs.")
            return approved

    def choose(self, question: Question) -> str | None:
        options = question.selection.options
        deadline = self._now() + question.timeout_s
        with self.pause():
            self._show(choice(question, question.timeout_s, self._width))
            given = self._choices.get(question.step_id or "")
            if given is not None:
                return self._given(question, given)
            if not self._is_terminal():
                raise RunAborted(
                    f"There is no terminal to choose at {_where(question)}: pass "
                    f"--choose {question.step_id or '<step id>'}=<1-{len(options)}|option id>.",
                    "no_answer",
                )
            return self._ask(question, deadline)

    def _ask(self, question: Question, deadline: float) -> str | None:
        options = question.selection.options
        while True:
            remaining = deadline - self._now()
            if remaining <= 0:
                self._timed_out(question)
                return None
            self._say(f"Choose [1-{len(options)}] ({clock(remaining)} left, q to stop): ", False)
            line = self._read_line(remaining)
            if line is None:
                self._say("")
                self._timed_out(question)
                return None
            if line == "":
                raise RunAborted(f"The input ended at {_where(question)}.", "no_answer")
            value = line.strip()
            if value.lower() in ("q", "quit"):
                self._say(f"Stopped at {_where(question)}.")
                raise RunAborted(f"Stopped by the operator at {_where(question)}.", "quit")
            chosen = _numbered(options, value)
            if chosen is not None:
                self._say(f"Chosen: {value} {chosen.label}")
                return chosen.id
            self._say(f"Type a number from 1 to {len(options)}, or q to stop.")

    def _given(self, question: Question, given: str) -> str:
        options = question.selection.options
        chosen = _numbered(options, given) or next((o for o in options if o.id == given), None)
        if chosen is None:
            raise RunAborted(
                f"--choose {question.step_id}={given} names no option at {_where(question)}: "
                f"give 1 to {len(options)}, or one of {', '.join(o.id for o in options)}.",
                "no_answer",
            )
        self._say(f"Choose [1-{len(options)}]: {chosen.label} (--choose)")
        return chosen.id

    def _timed_out(self, question: Question) -> None:
        self._say(f"No choice in time: {_where(question)} times out.")

    def _show(self, lines: list[str]) -> None:
        for index, line in enumerate(lines):
            styled = typer.style(line, bold=True) if index == 1 else line
            typer.echo(styled, color=self._colour)

    def _say(self, text: str, newline: bool = True) -> None:
        typer.echo(text, nl=newline, color=self._colour)


def _numbered(options: list[SelectionOption], value: str) -> SelectionOption | None:
    """The option numbered *value* from 1, if it is one."""
    if value.isdigit() and 1 <= int(value) <= len(options):
        return options[int(value) - 1]
    return None


def _where(question: Question) -> str:
    number = f"checkpoint {question.number} " if question.number else ""
    return f"{number}({question.step_id or 'a choice'})"


def parse_choices(entries: Sequence[str] | None) -> dict[str, str]:
    """``--choose`` entries (``<step_id>=<n|option id>``) by step id."""
    choices: dict[str, str] = {}
    for entry in entries or []:
        step_id, separator, value = entry.partition("=")
        if not separator or not step_id or not value:
            raise typer.BadParameter(f"expected <step_id>=<n|option id>, got {entry!r}")
        choices[step_id.strip()] = value.strip()
    return choices


@contextlib.contextmanager
def paused_display(progress: object) -> Iterator[None]:
    """Stop a live progress display while a window is up, and start it again after."""
    stop, start = getattr(progress, "stop", None), getattr(progress, "start", None)
    if callable(stop):
        stop()
    try:
        yield
    finally:
        if callable(start):
            start()

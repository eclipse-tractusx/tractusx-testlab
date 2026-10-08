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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The questions a run puts to its operator, and the answers that come back.

Pause and resume are the only other things an operator tells a running job, and
neither carries a value. ``flow/select`` (and ``connector/datasets/select``,
built on it) needs one: the option, out of the several it offers, the test goes
on with. The step asks here (:meth:`SelectionBoard.ask`) and blocks; whoever hosts the run — the
TestLab server, or an engine embedding the player — answers here
(:meth:`SelectionBoard.answer`) when the operator has chosen.

A run asks one question at a time, because it runs one step at a time. Every
method is meant for the loop the run runs on: the answer completes a future the
step awaits, and a future is not to be completed from another thread.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenQuestion:
    """What a run is waiting to be told: which step asks, and the option ids it accepts."""

    step_id: str | None
    options: tuple[str, ...]
    answer: asyncio.Future[str]


class SelectionBoard:
    """The open question of each job, by job id."""

    __slots__ = ("_open",)

    def __init__(self) -> None:
        self._open: dict[str, OpenQuestion] = {}

    def ask(self, job_id: str, step_id: str | None, options: Iterable[str]) -> asyncio.Future[str]:
        """Open a question for *job_id*; the returned future completes with the chosen id.

        A question the job left open is closed first: its step is no longer
        running, or it would not be asking again.
        """
        self.close(job_id)
        answer: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._open[job_id] = OpenQuestion(step_id, tuple(options), answer)
        return answer

    def pending(self, job_id: str) -> OpenQuestion | None:
        """The question *job_id* is waiting on, or ``None``."""
        question = self._open.get(job_id)
        return question if question is not None and not question.answer.done() else None

    def answer(self, job_id: str, value: str, step_id: str | None = None) -> None:
        """Answer *job_id*'s open question with the option id *value*.

        *step_id*, when given, has to name the step that asks: an answer
        meant for a question that has since been replaced is refused rather
        than taken for the new one.

        Raises:
            LookupError: the job is not waiting for a selection, or not at *step_id*.
            ValueError: *value* is not one of the options the step offered.
        """
        question = self.pending(job_id)
        if question is None:
            raise LookupError(f"Job '{job_id}' is not waiting for a selection")
        if step_id is not None and step_id != question.step_id:
            raise LookupError(
                f"Job '{job_id}' is waiting for a selection at step "
                f"'{question.step_id}', not '{step_id}'"
            )
        if value not in question.options:
            raise ValueError(
                f"'{value}' is not one of the options offered: {', '.join(question.options)}"
            )
        question.answer.set_result(value)

    def close(self, job_id: str) -> None:
        """Withdraw *job_id*'s question; a step still waiting on it sees it cancelled."""
        question = self._open.pop(job_id, None)
        if question is not None and not question.answer.done():
            question.answer.cancel()

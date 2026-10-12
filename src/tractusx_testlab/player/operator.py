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

"""A person in front of the run: approving its checkpoints, answering its choices (ADR-0028).

The player never asks anyone anything on its own. A host that embeds it — the
Catena-X engine — shows the briefing in its own UI before it starts a run and
answers ``flow/select`` through the job's question board
(``JobManager.selections``), as it always has; :meth:`TestlabPlayer.run_tck`
neither prompts, nor reads stdin, nor writes to stdout.

A host that has a person at hand instead — ``testlab run`` in a terminal —
gives :func:`run_with_operator` an :class:`Operator`. It is shown the run's
checkpoints before anything starts, and the run starts only if it approves;
and every time a step asks the operator to choose, it is asked, on a worker
thread, and its answer goes to the same question board the engine answers on.
The run itself cannot tell the two apart.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry
from tractusx_testlab.models.runtime.selection import Selection
from tractusx_testlab.player.execution._skip import resolve_skip_ids

if TYPE_CHECKING:
    from tractusx_testlab.authoring.test import Tck
    from tractusx_testlab.models import TckResult
    from tractusx_testlab.player.execution.player import TestlabPlayer


class RunDeclined(Exception):
    """The operator did not approve the run's checkpoints; no test ran."""


class RunAborted(Exception):
    """The operator stopped the run at a choice.

    ``reason`` is ``quit`` when they asked to, ``no_answer`` when there was no
    way to ask them and no answer given up front.
    """

    def __init__(self, message: str, reason: str = "quit") -> None:
        super().__init__(message)
        self.reason = reason
        #: The run's verdict, as far as it went: its teardowns ran.
        self.result: TckResult | None = None


@dataclass(frozen=True)
class Question:
    """A choice put to the operator, with the checkpoint it is.

    ``number`` is the checkpoint's place in the run from 1 and ``total`` how
    many the run has; ``entry`` is ``None`` for a question no checkpoint is
    about (a step a test switched off with ``checkpoint: false``).
    """

    job_id: str
    step_id: str | None
    selection: Selection
    timeout_s: float
    number: int | None = None
    total: int = 0
    entry: CheckpointEntry | None = None


class Operator(Protocol):
    """Whoever approves a run's checkpoints and answers its choices."""

    def approve(self, checkpoints: Sequence[CheckpointEntry]) -> bool:
        """Whether the run may start, having been shown *checkpoints* (never empty)."""
        ...

    def choose(self, question: Question) -> str | None:
        """The id of the option chosen, ``None`` when the time ran out.

        Blocks; called on a worker thread. Raises :class:`RunAborted` to stop the run.
        """
        ...


async def run_with_operator(
    player: TestlabPlayer,
    tck: Tck,
    operator: Operator,
    runtime_vars: dict | None = None,
    job_id: str | None = None,
) -> TckResult:
    """Run *tck* as :meth:`TestlabPlayer.run_tck` does, with *operator* approving and choosing.

    Raises :class:`RunDeclined` before anything starts when the operator does
    not approve, and :class:`RunAborted` after the run was stopped at a choice.
    """
    checkpoints = tck.checkpoints(resolve_skip_ids(tck, runtime_vars))
    if checkpoints and not operator.approve(checkpoints):
        raise RunDeclined(f"The run of {tck.name} was not approved; no test ran.")
    desk = _Desk(player, operator, asyncio.get_running_loop())
    player.monitor.add_callback(desk)
    try:
        result = await player.run_tck(tck, runtime_vars=runtime_vars, job_id=job_id)
    finally:
        player.monitor.remove_callback(desk)
        await desk.settle()
    if desk.aborted is not None:
        desk.aborted.result = result
        raise desk.aborted
    return result


@dataclass
class _Desk:
    """Puts the run's choices to the operator and hands their answers to the run."""

    player: TestlabPlayer
    operator: Operator
    loop: asyncio.AbstractEventLoop
    planned: list[CheckpointEntry] = field(default_factory=list)
    asking: dict[str, asyncio.Future[Any]] = field(default_factory=dict)
    aborted: RunAborted | None = None

    def __call__(self, event: str, payload: dict[str, Any]) -> None:
        if event == "checkpoints.planned":
            self.planned = [CheckpointEntry.model_validate(p) for p in payload["checkpoints"]]
        elif event == "step.selecting" and payload["job_id"] not in self.asking:
            self._ask(payload)

    def _ask(self, payload: dict[str, Any]) -> None:
        ref = payload.get("checkpoint") or {}
        index = ref.get("index")
        question = Question(
            job_id=payload["job_id"],
            step_id=payload.get("step_id"),
            selection=Selection.model_validate(payload["selection"]),
            timeout_s=float(payload["timeout_s"]),
            number=None if index is None else index + 1,
            total=len(self.planned),
            entry=self.planned[index] if index is not None and index < len(self.planned) else None,
        )
        asked = self.loop.run_in_executor(None, self.operator.choose, question)
        self.asking[question.job_id] = asked
        asked.add_done_callback(lambda done: self._answer(question, done))

    def _answer(self, question: Question, done: asyncio.Future[Any]) -> None:
        self.asking.pop(question.job_id, None)
        jobs = self.player.jobs
        error = done.exception()
        if isinstance(error, RunAborted):
            self.aborted = error
            jobs.cancel(question.job_id)
        elif error is not None:  # the operator could not be asked: stop, saying why
            self.aborted = RunAborted(f"The operator could not be asked: {error}", "error")
            jobs.cancel(question.job_id)
        elif done.result() is not None:
            try:
                jobs.selections.answer(question.job_id, done.result(), question.step_id)
            except LookupError:  # the question closed meanwhile: it timed out
                return

    async def settle(self) -> None:
        """Wait for a question still being asked, so no thread outlives the run."""
        if self.asking:
            await asyncio.wait(list(self.asking.values()))

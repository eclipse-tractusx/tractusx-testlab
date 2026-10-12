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

"""The step a coroutine is running, and which run of it this is.

A step reports what it does — a call, a wait, an answer — through the context
it is given, and the context is shared by every step of a test, nested ones
included. What tells two of them apart is where they sit (``path``) and which
run of that position this is (``attempt``). The runner opens a frame for each
step it runs, top-level or nested, and the frame is kept in a ``ContextVar``:
whatever the step publishes while it runs — on the event loop or in a worker
thread ``asyncio.to_thread`` started — reads it from there.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

#: Where a step sits: phase, index, then ``with:`` key and index per nesting level.
StepPath = tuple[str | int, ...]


@dataclass
class StepFrame:
    """One run of one step.

    ``attempt`` counts the runs of this position in the job, from 1 — a step a
    ``flow/retry`` runs again, or whose test is run again, counts up.
    ``checkpoint`` is the index of the checkpoint the step is, if it is one, and
    ``checkpoint_attempt`` the attempt of that checkpoint this run is. ``asked``,
    ``answered`` and ``pauses`` are what happened to that question in this run:
    a question asked again after a pause is the same attempt, ``pauses`` later.
    """

    test_id: str
    path: StepPath
    attempt: int
    checkpoint: int | None = None
    checkpoint_attempt: int = 0
    asked: bool = False
    answered: bool = False
    ended: bool = False
    pauses: int = 0


_current: ContextVar[StepFrame | None] = ContextVar("testlab_step_frame", default=None)


def current_frame() -> StepFrame | None:
    """The step the calling coroutine runs, or ``None`` outside one."""
    return _current.get()


def enter(frame: StepFrame) -> Token[StepFrame | None]:
    """Make *frame* the current step; returns the token :func:`leave` takes."""
    return _current.set(frame)


def leave(token: Token[StepFrame | None]) -> None:
    """Restore the step that was current before :func:`enter`."""
    _current.reset(token)

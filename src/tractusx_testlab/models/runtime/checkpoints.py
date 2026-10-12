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

"""A run's checkpoints: where it has someone act, and how that went (ADR-0027).

:class:`CheckpointEntry` is one checkpoint as a package states it — what
``Tck.checkpoints()`` and ``testlab inspect --checkpoints`` list, in run order.
:class:`CheckpointStatus` is that entry during a run: its ``state``, how many
times it was asked, and when. :class:`CheckpointRef` is what an exchange at a
checkpoint carries, so a reader can tell which checkpoint and which attempt a
call, an inbound request or a choice belongs to.

States:

* ``ahead`` — not asked yet;
* ``now`` — asked, and waiting for whoever has to act;
* ``cleared`` — answered, and its step completed;
* ``timed_out`` — a question nobody answered in time;
* ``failed`` — its step failed after the answer, or while it was being asked;
* ``skipped`` — its step was skipped, or not needed (a ``flow/if`` branch not
  taken, a choice with one option taken without asking);
* ``not_reached`` — its test stopped before it, or the run ended first.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from tractusx_testlab.models.primitives.checkpoint import CheckpointKind, Direction, Via

CheckpointState = Literal[
    "ahead", "now", "cleared", "timed_out", "failed", "skipped", "not_reached"
]


class CheckpointEntry(BaseModel):
    """One checkpoint of a package, in run order.

    ``position`` says where the step sits: its phase, its index there, then for
    a step a flow step carries the ``with:`` key and the index under it —
    ``execution/2/then/0``. ``label`` and ``description`` are the test's
    (``checkpoint:``), else the step's ``action``; text that still holds a
    ``${{ }}`` template is left out, being known only once the run resolves it.
    ``timeout_s`` is the step's, its default when the test gives none.
    """

    model_config = ConfigDict(frozen=True)

    test_id: str
    test_name: str
    phase: str
    position: str
    step_id: str | None = None
    uses: str
    direction: Direction
    kind: CheckpointKind
    via: Via | None = None
    name: str | None = None
    label: str | None = None
    description: str | None = None
    timeout_s: int | None = None
    #: The step sits in a ``flow/if`` branch: the run may not ask it.
    conditional: bool = False
    #: The step sits in a ``flow/retry`` (or a loop): the run may ask it more than once.
    repeated: bool = False


class CheckpointStatus(CheckpointEntry):
    """A checkpoint during a run: the entry, and how the run got on with it.

    ``attempts`` counts the asks; a question asked again after a pause is the
    same attempt. ``asked_at`` is the latest ask, ``answered_at`` when that
    attempt was answered or ended, and ``response_s`` how long the question was
    open until it was answered — the time the run was paused not counted.
    """

    state: CheckpointState = "ahead"
    attempts: int = 0
    asked_at: datetime | None = None
    answered_at: datetime | None = None
    response_s: float | None = None


class CheckpointRef(BaseModel):
    """Which checkpoint, and which attempt of it, an exchange belongs to."""

    model_config = ConfigDict(frozen=True)

    index: int
    attempt: int
    direction: Direction

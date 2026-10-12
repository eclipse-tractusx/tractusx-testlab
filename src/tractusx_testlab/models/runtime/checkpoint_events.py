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

"""The events of a run's checkpoints — the plan once, then every change (ADR-0027).

Kept beside ``events`` rather than in it only for its length; ``events``
re-exports them, and ``ExecutionEvent`` includes them.
"""

from __future__ import annotations

from typing import Literal

from tractusx_testlab.models.primitives.enums import EventKind
from tractusx_testlab.models.runtime._event_base import _ExecutionEvent
from tractusx_testlab.models.runtime.checkpoints import CheckpointStatus


class CheckpointsPlannedEvent(_ExecutionEvent):
    """Every checkpoint the run will meet, in run order, each ``ahead``.

    Published once, right after ``job_started`` and before any test starts.
    A checkpoint's ``index`` in every later event is its place in this list.
    """

    kind: Literal[EventKind.CHECKPOINTS_PLANNED] = EventKind.CHECKPOINTS_PLANNED
    checkpoints: list[CheckpointStatus]


class CheckpointUpdatedEvent(_ExecutionEvent):
    """One checkpoint changed: published right after the event that changed it.

    ``revision`` counts this checkpoint's updates from 1, so two updates of
    one checkpoint never carry the same data. ``cause`` is the ``kind`` of the
    event that changed it — ``step_waiting``, ``step_received``,
    ``step_completed``, ``test_started``, ``job_failed`` … — and
    ``cause_sequence`` that event's ``sequence`` in the player's own trace,
    when it writes one. A change no event of its own announces (a nested step
    starting, a ``flow/if`` branch not taken) has neither.
    """

    kind: Literal[EventKind.CHECKPOINT_UPDATED] = EventKind.CHECKPOINT_UPDATED
    index: int
    revision: int
    cause: str | None = None
    cause_sequence: int | None = None
    checkpoint: CheckpointStatus

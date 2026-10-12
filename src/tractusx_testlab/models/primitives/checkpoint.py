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

"""What a step type declares about being a checkpoint (ADR-0027).

A checkpoint is a step at which the run has someone act, and its direction
says who and which way:

* ``inbound`` — the system under test calls the Test Suite, and the Test Suite
  answers (``mock/wait/http_request``, ``mock/wait/dataplane/http_request``);
* ``outbound`` — the Test Suite calls the system under test, which has to be
  ready to answer (``notification/consumer/send``: a push the SUT must accept);
* ``internal`` — the move happens inside the Test Suite: the operator decides in
  its UI, and nothing is called either way (``flow/select``,
  ``connector/datasets/select``).

A step type declares it on its ``@step`` decorator::

    @step("mock/wait/http_request", checkpoint=Checkpoint(direction=Direction.INBOUND))

and a TCK author marks any other step, or switches one off, with the step's
``checkpoint:`` key (``models.authoring.checkpoint_mark``).

The engine and its viewers still read a checkpoint's ``kind`` (``wait`` or
``select``) and ``via``; both follow from the declaration, here and nowhere else:

===============  ==========  =========================================
direction        ``kind``    ``via``
===============  ==========  =========================================
``inbound``      ``wait``    ``direct`` unless the step says ``dataplane``
``outbound``     ``wait``    as the step says, else none
``internal``     ``select``  none
===============  ==========  =========================================
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class Direction(StrEnum):
    """Which way the move at a checkpoint goes."""

    #: The system under test calls the Test Suite, and the Test Suite answers.
    INBOUND = "inbound"
    #: The Test Suite calls the system under test, and the system under test answers.
    OUTBOUND = "outbound"
    #: Inside the Test Suite: the operator decides, nothing is called either way.
    INTERNAL = "internal"


class Via(StrEnum):
    """How a call at a checkpoint reaches its counterpart."""

    #: Straight to the address, without a connector in between.
    DIRECT = "direct"
    #: Through a connector's data plane, after a negotiation.
    DATAPLANE = "dataplane"


#: The engine's name for a checkpoint, kept for its viewers (``BriefingMoveKind``).
CheckpointKind = Literal["wait", "select"]


class NestedRun(StrEnum):
    """How a flow step runs the steps it carries under one of its ``with:`` keys."""

    #: Only when its branch is taken (``flow/if``'s ``then`` and ``else``).
    CONDITIONAL = "conditional"
    #: Possibly more than once (``flow/retry``, ``labs/flow/for_each``).
    REPEATED = "repeated"


class Checkpoint(BaseModel):
    """A checkpoint declaration: which way the move goes, and how a call travels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: Direction
    via: Via | None = None

    @model_validator(mode="before")
    @classmethod
    def _inbound_is_direct_unless_said(cls, data: Any) -> Any:
        """An inbound call reaches the Test Suite directly unless the step says otherwise."""
        if isinstance(data, dict) and data.get("direction") in (Direction.INBOUND, "inbound"):
            return {"via": Via.DIRECT, **data}
        return data

    @model_validator(mode="after")
    def _internal_travels_nowhere(self) -> Checkpoint:
        if self.direction is Direction.INTERNAL and self.via is not None:
            raise ValueError("an internal checkpoint calls nothing, so it has no 'via'")
        return self

    @property
    def kind(self) -> CheckpointKind:
        """``wait`` for a call either way, ``select`` for a move inside the Test Suite."""
        return "select" if self.direction is Direction.INTERNAL else "wait"

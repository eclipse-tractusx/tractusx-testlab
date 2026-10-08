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

"""A choice put to the operator — the ``step_selecting`` / ``step_selected`` events.

``flow/select`` and the steps built on it (``connector/datasets/select``) stop
the run when the test cannot decide on its own, and ask whoever drives it:
these are the question and the answer. Kept beside ``events`` rather than in
it only for its length; ``events`` re-exports them, and ``ExecutionEvent``
includes them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from tractusx_testlab.models.primitives.enums import EventKind
from tractusx_testlab.models.runtime._event_base import _ExecutionEvent
from tractusx_testlab.models.runtime.listener import WaitAction

#: How a host shows the options. ``dropdown``: a plain list of labels.
#: ``catalog_offers``: one card per asset and offer pair, each option's
#: ``details`` carrying ``asset_id``, ``offer_id``, ``properties`` and ``policy``.
SelectionPresentation = Literal["dropdown", "catalog_offers"]


class SelectionOption(BaseModel):
    """One answer the operator may give."""

    #: What the host answers with; unique among the options.
    id: str
    label: str
    description: str | None = None
    #: Whatever the operator needs to tell the options apart, shaped by the
    #: selection's ``presentation``.
    details: dict[str, Any] = Field(default_factory=dict)


class Selection(BaseModel):
    """Options put to the operator to choose exactly one."""

    presentation: SelectionPresentation = "dropdown"
    options: list[SelectionOption]
    #: What the test author says the choice is for (``with.action``).
    action: WaitAction | None = None


class StepSelectingEvent(_ExecutionEvent):
    """A step is blocked until the operator chooses one option, for at most ``timeout_s``.

    Answered through the player (``JobManager.selections``) with one of the
    options' ``id``. A pause stops the clock; the question stays open.
    """

    kind: Literal[EventKind.STEP_SELECTING] = EventKind.STEP_SELECTING
    test_id: str
    step_id: str | None = None
    step_type: str
    selection: Selection
    timeout_s: float


class StepSelectedEvent(_ExecutionEvent):
    """The operator chose; ``waited_ms`` is how long the step waited for it."""

    kind: Literal[EventKind.STEP_SELECTED] = EventKind.STEP_SELECTED
    test_id: str
    step_id: str | None = None
    step_type: str
    option: SelectionOption
    waited_ms: int

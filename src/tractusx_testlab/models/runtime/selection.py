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

"""An asset put to the operator to choose — the ``step_selecting`` / ``step_selected`` events.

``connector/query_catalog/select_asset`` reads a catalog that offers more than
one asset and cannot tell on its own which one the test is about. It stops and
asks whoever drives the run: these are the question and the answer. Kept beside
``events`` rather than in it only for its length; ``events`` re-exports them,
and ``ExecutionEvent`` includes them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from tractusx_testlab.models.primitives.enums import EventKind
from tractusx_testlab.models.runtime._event_base import _ExecutionEvent
from tractusx_testlab.models.runtime.listener import WaitAction


class SelectionOption(BaseModel):
    """One asset the operator may choose: what it is, and on what terms it is offered."""

    asset_id: str
    #: The dataset's public properties as the catalog writes them — its type,
    #: subject, version, semantic id and any other — without its offers and
    #: distributions, which are not what the asset *is*.
    properties: dict[str, Any] = Field(default_factory=dict)
    #: The offers the asset is published under (``odrl:hasPolicy``), as the
    #: catalog writes them: each with its permissions, prohibitions and
    #: obligations. An asset is often offered more than once.
    policies: list[dict[str, Any]] = Field(default_factory=list)


class AssetSelection(BaseModel):
    """A catalog's assets, put to the operator to choose exactly one."""

    #: The DSP address of the connector whose catalog was read.
    counter_party_address: str
    #: The connector's dataspace identity — a DID or a BPNL.
    counter_party_id: str
    options: list[SelectionOption]
    #: What the test author says the choice is for (``with.action``).
    action: WaitAction | None = None


class StepSelectingEvent(_ExecutionEvent):
    """A step is blocked until the operator chooses one asset, for at most ``timeout_s``.

    Answered through the player (``JobManager.selections``) with one of the
    options' ``asset_id``. A pause stops the clock; the question stays open.
    """

    kind: Literal[EventKind.STEP_SELECTING] = EventKind.STEP_SELECTING
    test_id: str
    step_id: str | None = None
    step_type: str
    selection: AssetSelection
    timeout_s: float


class StepSelectedEvent(_ExecutionEvent):
    """The operator chose an asset; ``waited_ms`` is how long the step waited for it."""

    kind: Literal[EventKind.STEP_SELECTED] = EventKind.STEP_SELECTED
    test_id: str
    step_id: str | None = None
    step_type: str
    asset_id: str
    waited_ms: int

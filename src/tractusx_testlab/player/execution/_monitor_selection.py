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

"""The question-to-the-operator half of the ExecutionMonitor.

``connector/query_catalog/select_asset`` stops the run until the operator picks
one asset of a catalog. That is two moments, asked and answered, published as
``step_selecting`` and ``step_selected`` and traced as
``tck.test.step.selecting`` / ``tck.test.step.selected``. A mixin beside
``StepEvents`` for the same reason that one is: ``ExecutionMonitor`` stays the
one place an event is built.
"""

from __future__ import annotations

from tractusx_testlab.models.runtime.events import ExecutionEvent
from tractusx_testlab.models.runtime.selection import (
    AssetSelection,
    StepSelectedEvent,
    StepSelectingEvent,
)
from tractusx_testlab.player.execution._trace_publisher import TracePublisher


class SelectionEvents:
    """The ``on_step_selecting`` / ``on_step_selected`` methods, mixed into the monitor."""

    __slots__ = ()

    _trace: TracePublisher

    def _publish(self, event: ExecutionEvent, event_id: str | None = None) -> None:
        raise NotImplementedError

    def on_step_selecting(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        selection: AssetSelection,
        timeout_s: float,
    ) -> None:
        """Publish that the run waits for the operator to choose one asset, for at most *timeout_s*.

        Published again, with what is left of the timeout, when a pause ends:
        the question is still open.
        """
        event = StepSelectingEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            step_type=step_type,
            selection=selection,
            timeout_s=timeout_s,
        )
        event_id = self._trace.emit(
            "tck.test.step.selecting",
            {
                "attempt": 1,
                "selection": event.selection.model_dump(mode="json"),
                "timeout_s": timeout_s,
            },
            source=step_type,
            scope=(test, phase, step_id or step_type.rsplit("/", 1)[-1]),
        )
        self._publish(event, event_id)

    def on_step_selected(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        asset_id: str,
        waited_ms: int,
    ) -> None:
        """Publish which asset the operator chose, and how long the run waited for it."""
        event = StepSelectedEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            step_type=step_type,
            asset_id=asset_id,
            waited_ms=waited_ms,
        )
        event_id = self._trace.emit(
            "tck.test.step.selected",
            {"attempt": 1, "asset_id": asset_id, "waited_ms": waited_ms},
            source=step_type,
            scope=(test, phase, step_id or step_type.rsplit("/", 1)[-1]),
        )
        self._publish(event, event_id)

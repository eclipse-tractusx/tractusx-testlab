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

``flow/select`` (and ``connector/datasets/select``) stops the run until the
operator picks one option. That is two moments, asked and answered, published as
``step_selecting`` and ``step_selected`` and traced as
``tck.test.step.selecting`` / ``tck.test.step.selected``. A mixin beside
``StepEvents`` for the same reason that one is: ``ExecutionMonitor`` stays the
one place an event is built.

At an internal checkpoint (ADR-0028) they are its moments: what was offered,
and what was chosen, each naming the checkpoint and its attempt. A question
put again after a pause is the same attempt, ``pauses`` later.
"""

from __future__ import annotations

from tractusx_testlab.models.runtime.selection import (
    Selection,
    SelectionOption,
    StepSelectedEvent,
    StepSelectingEvent,
)
from tractusx_testlab.player.checkpoints import current_frame
from tractusx_testlab.player.execution._monitor_checkpoints import CheckpointEvents


class SelectionEvents(CheckpointEvents):
    """The ``on_step_selecting`` / ``on_step_selected`` methods, mixed into the monitor."""

    __slots__ = ()

    def on_step_selecting(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        selection: Selection,
        timeout_s: float,
    ) -> None:
        """Publish that the run waits for the operator to choose one option, for at most *timeout_s*.

        Published again, with what is left of the timeout, when a pause ends:
        the question is still open.
        """
        frame = current_frame()
        if frame is not None and frame.asked:  # only a pause puts the question again
            self._follow("suspended")
        attempt, ref, pauses = self._marks()
        event = StepSelectingEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            attempt=attempt,
            checkpoint=ref,
            step_type=step_type,
            selection=selection,
            timeout_s=timeout_s,
            pauses=pauses,
        )
        data = {"selection": event.selection.model_dump(mode="json"), "timeout_s": timeout_s}
        event_id = self._trace.step_event(
            "tck.test.step.selecting",
            test,
            step_id,
            step_type,
            phase,
            data,
            self._trace_marks(attempt, ref, pauses),
        )
        self._publish(event, event_id)
        self._follow("asked", self._cause(event.kind.value))

    def on_step_selected(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        option: SelectionOption,
        waited_ms: int,
    ) -> None:
        """Publish which option the operator chose, and how long the run waited for it."""
        attempt, ref, pauses = self._marks()
        event = StepSelectedEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            attempt=attempt,
            checkpoint=ref,
            step_type=step_type,
            option=option,
            waited_ms=waited_ms,
        )
        data = {
            "value": option.id,
            "option": event.option.model_dump(mode="json"),
            "waited_ms": waited_ms,
        }
        event_id = self._trace.step_event(
            "tck.test.step.selected",
            test,
            step_id,
            step_type,
            phase,
            data,
            self._trace_marks(attempt, ref, pauses),
        )
        self._publish(event, event_id)
        self._follow("answered", self._cause(event.kind.value), waited_ms)

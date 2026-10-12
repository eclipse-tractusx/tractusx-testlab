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

"""The inbound half of the ExecutionMonitor's step events.

An address opened for the system under test (``step_listening``), the run
blocked on it (``step_waiting``), the wait stopped for a pause
(``step_suspended``) and the call that arrived, with how the Test Suite
answered it (``step_received``). At an inbound checkpoint these are its
moments: asked, paused, answered (ADR-0028). A mixin beside ``StepEvents`` for
the same reason that one is: ``ExecutionMonitor`` stays the one place an event
is built.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.logging import wire
from tractusx_testlab.models.runtime.events import (
    StepListeningEvent,
    StepReceivedEvent,
    StepSuspendedEvent,
    StepWaitingEvent,
)
from tractusx_testlab.models.runtime.results import CallbackResult
from tractusx_testlab.player.execution._monitor_checkpoints import CheckpointEvents
from tractusx_testlab.player.execution._trace_publisher import received_data


class InboundEvents(CheckpointEvents):
    """The ``on_step_listening`` … ``on_step_received`` methods, mixed into the monitor."""

    __slots__ = ()

    def on_step_listening(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        listener: Any,
    ) -> None:
        """Publish that an address is open for the SUT to call, and which one.

        ``mock/api`` has registered the endpoint. The method and the URL are
        the payload, because this is the moment a person driving the SUT by
        hand needs to be told where to call
        (:class:`~tractusx_testlab.models.runtime.events.StepListeningEvent`).
        """
        attempt, ref, pauses = self._marks()
        event = StepListeningEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            attempt=attempt,
            checkpoint=ref,
            step_type=step_type,
            listener=listener,
        )
        data = {"listener": event.listener.model_dump(mode="json")}
        event_id = self._trace.step_event(
            "tck.test.step.listening",
            test,
            step_id,
            step_type,
            phase,
            data,
            self._trace_marks(attempt, ref, pauses),
        )
        self._publish(event, event_id)

    def on_step_waiting(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        listener: Any,
        timeout_s: float,
    ) -> None:
        """Publish that the run is now blocked on that address, for at most *timeout_s*.

        The inbound checkpoint the step is, is asked now — or, after a pause,
        asked again: the same attempt, ``pauses`` later.
        """
        attempt, ref, pauses = self._marks()
        event = StepWaitingEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            attempt=attempt,
            checkpoint=ref,
            step_type=step_type,
            listener=listener,
            timeout_s=timeout_s,
            pauses=pauses,
        )
        data = {"listener": event.listener.model_dump(mode="json"), "timeout_s": timeout_s}
        event_id = self._trace.step_event(
            "tck.test.step.waiting",
            test,
            step_id,
            step_type,
            phase,
            data,
            self._trace_marks(attempt, ref, pauses),
        )
        self._publish(event, event_id)
        self._follow("asked", self._cause(event.kind.value))

    def on_step_suspended(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        listener: Any,
        remaining_s: float,
        waited_ms: int,
    ) -> None:
        """Publish that a wait stopped counting for a pause, with *remaining_s* left."""
        self._follow("suspended")
        attempt, ref, pauses = self._marks()
        event = StepSuspendedEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            attempt=attempt,
            checkpoint=ref,
            step_type=step_type,
            listener=listener,
            remaining_s=remaining_s,
            waited_ms=waited_ms,
            pauses=pauses,
        )
        data = {
            "listener": event.listener.model_dump(mode="json"),
            "remaining_s": remaining_s,
            "waited_ms": waited_ms,
        }
        event_id = self._trace.step_event(
            "tck.test.step.suspended",
            test,
            step_id,
            step_type,
            phase,
            data,
            self._trace_marks(attempt, ref, pauses),
        )
        self._publish(event, event_id)

    def on_step_received(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        listener: Any,
        request: CallbackResult,
        waited_ms: int,
    ) -> None:
        """Publish that the call a step was waiting for has arrived, and how it was answered.

        What arrived is the SUT's to send, and it is published before the step
        that waited on it returns — before anything learned which of it is a
        credential. So it is redacted here, the way a recorded call is: the
        headers, the query and the body by the names they carry (logging.wire),
        and the Test Suite's answer body the same way — a mock answering a token
        endpoint answers with one. The step itself is handed the call as it
        came. At an inbound checkpoint this is the exchange, and it answers the
        question — unless the call was turned away (``refused``), which is no
        answer: the checkpoint is not cleared, and the step fails on it.
        """
        answer = request.response
        request = request.model_copy(
            update={
                "headers": wire.safe_headers(request.headers),
                "query_params": wire.redact_secrets(request.query_params),
                "payload": wire.redact_secrets(request.payload),
                "response": None
                if answer is None
                else answer.model_copy(update={"body": wire.redact_secrets(answer.body)}),
            }
        )
        attempt, ref, pauses = self._marks()
        event = StepReceivedEvent(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            attempt=attempt,
            checkpoint=ref,
            step_type=step_type,
            listener=listener,
            request=request,
            waited_ms=waited_ms,
        )
        event_id = self._trace.step_event(
            "tck.test.step.received",
            test,
            step_id,
            step_type,
            phase,
            received_data(event.listener, request, waited_ms),
            self._trace_marks(attempt, ref, pauses),
        )
        self._publish(event, event_id)
        if request.refused is not None:
            self._follow("refused", self._cause(event.kind.value))
        else:
            self._follow("answered", self._cause(event.kind.value), waited_ms)

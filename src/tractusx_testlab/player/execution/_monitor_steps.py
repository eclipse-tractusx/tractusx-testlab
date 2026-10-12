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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The step lifecycle half of the ExecutionMonitor.

Everything a monitor publishes *about a step* — that it started, each call it
made, and how it ended — lives here; the inbound moments (the address it
opened, the wait it is blocked in, the call that arrived) are
:class:`~tractusx_testlab.player.execution._monitor_inbound.InboundEvents`. It is a mixin rather than a second publisher on
purpose: ``ExecutionMonitor`` stays the one place an event is built, and this
is that place's step-shaped half (docs/developer/execution-events.md).

Every event carries the step's marks (``CheckpointEvents._marks``): which run
of the step it is, and the checkpoint it is, if it is one. The moments of a
question — asked, paused, answered — are passed on to the run's checkpoints
right after they are published.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.logging import wire
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.events import (
    AssertionResultEvent,
    StepCallEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepSkippedEvent,
    StepStartedEvent,
)
from tractusx_testlab.models.runtime.results import HttpExchange, StepResult
from tractusx_testlab.player.execution._monitor_checkpoints import CheckpointEvents


class StepEvents(CheckpointEvents):
    """The ``on_step_*`` methods, mixed into :class:`ExecutionMonitor`.

    It reads the monitor's trace publisher and hands every event to the
    monitor's ``_publish``; both are the monitor's, declared on
    :class:`CheckpointEvents` only so the type checker can follow.
    """

    __slots__ = ()

    def on_step_started(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_index: int,
        step_type: str,
        step_name: str,
        phase: str = "main",
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Publish a step_started event.

        *inputs* is the step's ``with:`` block with its references resolved —
        the values the step is about to be given, not the template naming them —
        with every credential-named input shown as ``***`` (logging.wire). A
        checkpoint the step does not ask for itself is asked only once the step
        really runs — after its ``if:`` (``CheckpointTracker.begin``).
        """
        inputs = wire.redact_secrets(inputs)
        attempt, ref, pauses = self._marks()
        event_id = self._trace.step_started(
            test,
            step_id,
            step_index,
            step_type,
            phase,
            inputs,
            self._trace_marks(attempt, ref, pauses),
        )
        self._publish(
            StepStartedEvent(
                job_id=job_id,
                test_id=test,
                step_id=step_id,
                attempt=attempt,
                checkpoint=ref,
                step_index=step_index,
                step_type=step_type,
                step_name=step_name,
                phase=phase,
                inputs=inputs,
            ),
            event_id,
        )

    def on_step_call(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        step_type: str,
        phase: str,
        index: int,
        call: HttpExchange,
    ) -> None:
        """Publish one call a step made, as soon as its answer came back.

        While the step is still running, which is the point: a DSP pull polls a
        negotiation for a minute, and the polls are what somebody watching needs
        to see (:class:`~tractusx_testlab.models.runtime.events.StepCallEvent`).
        At an outbound checkpoint this is the exchange: what was sent, and how
        the system under test answered.
        """
        attempt, ref, pauses = self._marks()
        marks = self._trace_marks(attempt, ref, pauses)
        event_id = self._trace.step_call(test, step_id, step_type, phase, index, call, marks)
        self._publish(
            StepCallEvent(
                job_id=job_id,
                test_id=test,
                step_id=step_id,
                attempt=attempt,
                checkpoint=ref,
                step_type=step_type,
                index=index,
                call=call,
            ),
            event_id,
        )

    def on_step_completed(
        self,
        job_id: str,
        test: str,
        step_id: str | None,
        result: StepResult,
    ) -> None:
        """Publish one assertion_result event per assertion, then the step outcome.

        The outcome kind (step_completed / step_failed / step_skipped) is
        derived from ``result.status`` — the one place that status lives —
        so a consumer never has to sniff ``step_type`` to know what happened.
        """
        # What is written down is not what the run keeps: the record carries the
        # call the SDK really made, masked, while the result keeps the exchange
        # the step named — which is what a ``returns:`` block reads (logging.wire).
        record = wire.as_recorded(result)
        attempt, ref, pauses = self._marks()

        # The assertion lines are given the step's id on purpose: they have no
        # event of their own — ADR-0016 nests them in the terminal event, which
        # is where a reader following the id finds them.
        event_id = self._trace.step_ended(
            test, step_id, record, self._trace_marks(attempt, ref, pauses)
        )

        for index, assertion_result in enumerate(record.assertions):
            self._publish(
                AssertionResultEvent(
                    job_id=job_id,
                    test_id=test,
                    step_id=step_id,
                    attempt=attempt,
                    checkpoint=ref,
                    step_name=result.step_name,
                    index=index,
                    assertion=assertion_result,
                ),
                event_id,
            )

        outcome = {StepStatus.FAILED: StepFailedEvent, StepStatus.SKIPPED: StepSkippedEvent}.get(
            result.status, StepCompletedEvent
        )
        event = outcome(
            job_id=job_id,
            test_id=test,
            step_id=step_id,
            attempt=attempt,
            checkpoint=ref,
            result=record,
        )
        self._publish(event, event_id)
        self._follow("ended", result.status, self._cause(event.kind.value))

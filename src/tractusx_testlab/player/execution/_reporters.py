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
## It was reviewed and tested by a human committer.

"""What a phase binds on the context so a step can report while it runs.

A step knows what it did — the call it made, the address it opened, the
request that arrived; the phase runner knows the job, the script and the phase
it belongs to. These carry the second half to the monitor on the step's behalf
(contracts.CallReporter, contracts.ListenerReporter), and a step nested inside
a flow step reports through the same ones, because it runs on the same context.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor


def bind_reporters(
    context: StepContext, monitor: ExecutionMonitor, job_id: str, script: str, phase: str
) -> None:
    """Bind both directions of traffic — calls out, calls in — for one phase."""
    context.bind_call_reporter(
        lambda step_type, step_id, index, call: monitor.on_step_call(
            job_id, script, step_id, step_type, phase, index, call
        )
    )
    context.bind_listener_reporter(ListenerReports(monitor, job_id, script, phase))


class ListenerReports:
    """The inbound half of what a phase publishes for its steps."""

    __slots__ = ("_job_id", "_monitor", "_phase", "_script")

    def __init__(self, monitor: ExecutionMonitor, job_id: str, script: str, phase: str) -> None:
        self._monitor = monitor
        self._job_id = job_id
        self._script = script
        self._phase = phase

    def listening(self, step_type: str, step_id: str | None, listener: Any) -> None:
        self._monitor.on_step_listening(
            self._job_id, self._script, step_id, step_type, self._phase, listener
        )

    def waiting(self, step_type: str, step_id: str | None, listener: Any, timeout_s: float) -> None:
        self._monitor.on_step_waiting(
            self._job_id, self._script, step_id, step_type, self._phase, listener, timeout_s
        )

    def received(
        self,
        step_type: str,
        step_id: str | None,
        listener: Any,
        request: Any,
        waited_ms: int,
    ) -> None:
        self._monitor.on_step_received(
            self._job_id,
            self._script,
            step_id,
            step_type,
            self._phase,
            listener,
            request,
            waited_ms,
        )

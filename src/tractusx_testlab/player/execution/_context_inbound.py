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

"""The part of ``StepContext`` a step reports an inbound call through.

Opened, blocked on, suspended for a pause, arrived: the four moments the mock
steps publish (``contracts.ListenerReporter``). Split from the context only for
its length; ``StepContext`` is the one class that uses it.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.contracts import ListenerReporter


class InboundReporting:
    """Publishing an inbound call's moments through the phase's reporter, if one is bound."""

    __slots__ = ("_listener_reporter",)

    # ------------------------------------------------------------------
    # Reporting an inbound call: opened, blocked on, suspended, arrived
    # ------------------------------------------------------------------

    def bind_listener_reporter(self, reporter: ListenerReporter | None) -> None:
        """Give this context somewhere to publish an inbound call's two moments."""
        self._listener_reporter = reporter

    def report_listening(self, step_type: str, step_id: str | None, listener: Any) -> None:
        """Say that an address is open for the SUT to call — and which one."""
        if self._listener_reporter is not None:
            self._listener_reporter.listening(step_type, step_id, listener)

    def report_waiting(
        self, step_type: str, step_id: str | None, listener: Any, timeout_s: float
    ) -> None:
        """Say that the run is now blocked on that address, and for how long at most."""
        if self._listener_reporter is not None:
            self._listener_reporter.waiting(step_type, step_id, listener, timeout_s)

    def report_suspended(
        self,
        step_type: str,
        step_id: str | None,
        listener: Any,
        remaining_s: float,
        waited_ms: int,
    ) -> None:
        """Say that the wait stopped counting for a pause, and how much of it is left."""
        if self._listener_reporter is not None:
            self._listener_reporter.suspended(step_type, step_id, listener, remaining_s, waited_ms)

    def report_received(
        self,
        step_type: str,
        step_id: str | None,
        listener: Any,
        request: Any,
        waited_ms: int,
    ) -> None:
        """Say that the call arrived, and what it carried."""
        if self._listener_reporter is not None:
            self._listener_reporter.received(step_type, step_id, listener, request, waited_ms)

    # ------------------------------------------------------------------
    # Reporting a question to the operator: asked, answered
    # ------------------------------------------------------------------

    def report_selecting(
        self, step_type: str, step_id: str | None, selection: Any, timeout_s: float
    ) -> None:
        """Say that the run is blocked until the operator chooses one of *selection*'s options."""
        if self._listener_reporter is not None:
            self._listener_reporter.selecting(step_type, step_id, selection, timeout_s)

    def report_selected(
        self, step_type: str, step_id: str | None, option: Any, waited_ms: int
    ) -> None:
        """Say which option the operator chose, and how long the run waited for it."""
        if self._listener_reporter is not None:
            self._listener_reporter.selected(step_type, step_id, option, waited_ms)

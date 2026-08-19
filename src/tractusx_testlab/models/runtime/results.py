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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Result models — execution-time structures for steps, scripts, and TCKs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.models.primitives.enums import (
    AssertionSeverity,
    ScriptStatus,
    StepPhase,
    StepStatus,
)

#: Marks a ``StepResult.error`` whose failure came from TestLab, not from the SUT.
#:
#: There is no ``StepStatus.ERROR`` yet — adding one changes the event payload
#: the IDE consumes, so it lands in P4 with the rest of that contract. Until
#: then the distinction is carried in the message, which is at least visible in
#: the report instead of being lost entirely, and the trace turns it back into a
#: structured ``origin`` on the step's error (ADR-0016).
ENGINE_FAULT_PREFIX = "[engine fault] "


class HttpRequest(BaseModel):
    """Captured HTTP request details for a step execution."""

    method: str
    url: str
    headers: dict | None = None
    #: Query parameters passed alongside the URL rather than inside it. Recorded
    #: separately because that is how they were sent: folding them into ``url``
    #: would report a request nobody wrote.
    params: dict | None = None
    body: Any | None = None


class HttpResponse(BaseModel):
    """Captured HTTP response details from a step execution."""

    status_code: int
    headers: dict | None = None
    body: Any | None = None
    duration_ms: float = 0.0


class HttpExchange(BaseModel):
    """One request a step sent and the answer it got.

    A step is not one call. ``connector/consumer/pull_data_filtered`` runs a
    catalog query, a negotiation, a poll loop and a transfer before it returns
    anything, and when the SUT answers 403 to the first of them the only trace
    used to be the exception text. Every call the step makes is recorded here,
    in order, so the run can be debugged from the trace instead of re-run with
    a packet capture attached.

    ``failed`` marks the exchange whose transport raised — a refused
    connection, a timeout, a TLS failure. Those have a request and no response,
    which is exactly the case worth seeing.
    """

    request: HttpRequest
    response: HttpResponse | None = None
    error: str | None = None
    #: Who made the call: the SDK method for a call the SDK made on the engine's
    #: behalf (``CatalogController.get_catalog``), and ``testlab/http_client``
    #: for one the engine made itself. A step is several calls through two
    #: transports, and "which layer sent this" is the first question asked of a
    #: failing one.
    context: str | None = None
    started_at: datetime | None = None


class AssertionResult(BaseModel):
    """Result of evaluating a single assertion against step output."""

    assertion: Assertion
    passed: bool
    expected: Any | None = None
    actual: Any | None = None
    message: str = ""
    severity: AssertionSeverity = AssertionSeverity.HARD


class StepResult(BaseModel):
    """Execution result for a single test step."""

    step_name: str
    step_type: str = ""
    phase: StepPhase = StepPhase.EXECUTION
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_s: float | None = None
    #: What the step was actually given — its ``with:`` block after every
    #: ``${{ ... }}`` reference was resolved. Recorded because a step that failed
    #: on the value a reference resolved to cannot be debugged from the script,
    #: which only says which reference it wrote.
    inputs: dict | None = None
    #: The exchange the step is *about* — what a script asserts on and what the
    #: console prints. Set by the step itself; when the step did not name one,
    #: the runner fills it from the last recorded exchange so a step that raised
    #: before returning still reports what it sent.
    request: HttpRequest | None = None
    response: HttpResponse | None = None
    #: Every call the step made, in order. Written to the execution trace, not
    #: to the console: the console prints the subject exchange, the trace keeps
    #: the whole conversation (ADR-0016).
    exchanges: list[HttpExchange] = Field(default_factory=list)
    error: str | None = None
    #: What kind of failure this was, when the error named itself — the trace
    #: publishes it as ``errors[].code`` (ADR-0016). ``None`` leaves the code to
    #: be classified by origin alone: a verdict about the SUT, or an engine bug.
    error_code: str | None = None
    #: The evidence behind the message: the offers a policy was compared
    #: against, the states a poll loop saw. Published as ``errors[].context``,
    #: so the IDE renders the comparison instead of parsing it back out of a
    #: sentence.
    error_context: dict | None = None
    error_traceback: str | None = None
    output: Any | None = None
    assertions: list[AssertionResult] = Field(default_factory=list)


class CallbackResult(BaseModel):
    """Result of receiving (or timing out) a callback on a mock listener."""

    listener_name: str
    path: str
    method: str = "POST"
    headers: dict = Field(default_factory=dict)
    query_params: dict = Field(default_factory=dict)
    payload: Any | None = None
    received_at: datetime | None = None
    timed_out: bool = False


class AssertionSummary(BaseModel):
    """Aggregated assertion pass/fail counts for a script run."""

    #: Assertions the script's executed steps declared. Recorded separately from
    #: :attr:`total` so "checked nothing" is never indistinguishable from
    #: "checked everything and it passed" — the two used to produce the same
    #: ``RESULT: PASS`` with nothing to tell them apart.
    declared: int = 0
    total: int = 0
    passed: int = 0
    failed_hard: int = 0
    failed_soft: int = 0

    @property
    def verified_nothing(self) -> bool:
        """True when the run reached its end without evaluating a single check.

        Not an error on its own — a provisioning-only TCK legitimately asserts
        nothing — but it is never a certification, and a report that does not
        say so is telling the reader something it did not establish.
        """
        return self.total == 0

    @property
    def unevaluated(self) -> int:
        """Assertions a step declared and the engine did not evaluate.

        Always zero if the engine is behaving: assertions are evaluated one for
        one. A non-zero value means checks went missing between the script and
        the result, which is the shape of the defect this whole review began
        with, so it is measured rather than assumed.
        """
        return max(0, self.declared - self.total)


class ScriptResult(BaseModel):
    """Execution result for a complete test script."""

    script_id: str = ""
    script_name: str = ""
    dataspace_version: str = ""
    status: ScriptStatus = ScriptStatus.IDLE
    execution: list[StepResult] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_duration_s: float | None = None
    metadata: dict | None = None
    assertion_summary: AssertionSummary = Field(default_factory=AssertionSummary)
    callback_results: list[CallbackResult] = Field(default_factory=list)
    error: str | None = None


class TckResult(BaseModel):
    """Execution result for an entire TCK package."""

    tck_id: str = ""
    package_name: str = ""
    status: ScriptStatus = ScriptStatus.IDLE
    scripts: list[ScriptResult] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duration_ms(self) -> float | None:
        """Total TCK execution duration in milliseconds."""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds() * 1000
        return None

    @property
    def steps_passed(self) -> int:
        """Count of steps with PASSED status across all scripts.

        Named for what it is. It was ``passed``, which reads as a verdict, and
        one caller used it as one: ``if result.passed:`` decided whether to
        emit ``job_completed`` or ``job_failed``, and a non-zero *count* is
        truthy — so a run where four steps passed and one failed announced
        itself as COMPLETED on the event stream the IDE consumes, while the
        CLI printed FAIL from :attr:`status`. Ask :attr:`status` for the
        verdict; ask this for the tally.
        """
        return sum(
            1
            for script in self.scripts
            for step in script.execution
            if step.status == StepStatus.PASSED
        )

    @property
    def steps_total(self) -> int:
        """Total number of steps across all scripts."""
        return sum(len(script.execution) for script in self.scripts)

    @property
    def tck_name(self) -> str:
        """Alias for tck_id used as the display name."""
        return self.tck_id

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Tests for the typed execution events (C46).

The contract these hold to is the one in ``docs/developer/execution-events.md``:
every event carries a ``kind``, and ``kind`` is the only field a consumer reads
to decide what happened.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.paths import DOCS_DIR
from tractusx_testlab.models.authoring.definitions import Assertion, StepDefinition
from tractusx_testlab.models.primitives.enums import (
    AssertionSeverity,
    EventKind,
    StepStatus,
)
from tractusx_testlab.models.runtime.events import ExecutionEvent
from tractusx_testlab.models.runtime.results import (
    AssertionResult,
    HttpRequest,
    HttpResponse,
    ScriptResult,
    StepResult,
)
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.server.streaming.formatter import TERMINAL_EVENTS

_CONTRACT_PAGE = DOCS_DIR / "developer" / "execution-events.md"


@pytest.fixture()
def published() -> list[tuple[str, dict[str, Any]]]:
    return []


@pytest.fixture()
def monitor(published: list) -> ExecutionMonitor:
    mon = ExecutionMonitor(MagicMock())
    mon.add_callback(lambda event, payload: published.append((event, payload)))
    return mon


def _step_result(status: StepStatus, assertions: list | None = None) -> StepResult:
    return StepResult(
        step_name="[1/1] negotiate",
        step_type="connector/consumer/negotiate",
        status=status,
        assertions=assertions or [],
    )


def _assertion(passed: bool) -> AssertionResult:
    return AssertionResult(
        assertion=Assertion(uses="validate/assert", with_={"input": "status_code"}),
        passed=passed,
        expected=200,
        actual=200 if passed else 502,
        message="" if passed else "Expected 200, got 502",
        severity=AssertionSeverity.HARD,
    )


# ---------------------------------------------------------------------------
# The discriminator
# ---------------------------------------------------------------------------


class TestEventKindIsTheDiscriminator:
    def test_every_event_carries_its_kind(self, monitor: ExecutionMonitor, published: list) -> None:
        monitor.on_job_started("job-1", "ccm-tck")
        monitor.on_script_started("job-1", "script-1", 0)
        monitor.on_step_started(
            "job-1", "script-1", "neg", 0, "connector/consumer/negotiate", "[1/1] neg"
        )
        monitor.on_job_completed("job-1")

        assert all("kind" in payload for _, payload in published)

    def test_the_wire_name_is_the_kind_with_a_dot(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        monitor.on_step_completed("job-1", "script-1", "neg", _step_result(StepStatus.PASSED))
        event, payload = published[-1]
        assert event == "step.completed"
        assert payload["kind"] == EventKind.STEP_COMPLETED.value

    def test_a_step_type_is_never_an_outcome(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        """The outcome is the kind; step_type only names which step ran."""
        monitor.on_step_completed("job-1", "script-1", "neg", _step_result(StepStatus.FAILED))
        _, payload = published[-1]
        assert payload["kind"] == EventKind.STEP_FAILED.value
        assert payload["result"]["step_type"] == "connector/consumer/negotiate"

    def test_every_declared_kind_has_a_payload_model(self) -> None:
        """A kind with no model could be emitted as an untyped dict."""
        modelled = {member.model_fields["kind"].default for member in ExecutionEvent.__args__}
        assert modelled == set(EventKind)


# ---------------------------------------------------------------------------
# Step outcomes
# ---------------------------------------------------------------------------


class TestStepOutcome:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (StepStatus.PASSED, "step.completed"),
            (StepStatus.FAILED, "step.failed"),
            (StepStatus.SKIPPED, "step.skipped"),
        ],
    )
    def test_the_outcome_kind_follows_the_result_status(
        self,
        monitor: ExecutionMonitor,
        published: list,
        status: StepStatus,
        expected: str,
    ) -> None:
        monitor.on_step_completed("job-1", "script-1", "neg", _step_result(status))
        assert published[-1][0] == expected


class TestAssertionEvents:
    def test_one_event_per_assertion_ahead_of_the_step_outcome(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        monitor.on_step_completed(
            "job-1",
            "script-1",
            "neg",
            _step_result(StepStatus.PASSED, [_assertion(True), _assertion(True)]),
        )

        assert [event for event, _ in published] == [
            "assertion.result",
            "assertion.result",
            "step.completed",
        ]

    def test_an_assertion_reports_its_own_outcome(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        """This is what replaces guessing at an assertion from the step type."""
        monitor.on_step_completed(
            "job-1",
            "script-1",
            "neg",
            _step_result(StepStatus.FAILED, [_assertion(False)]),
        )
        _, payload = published[0]
        assert payload["kind"] == EventKind.ASSERTION_RESULT.value
        assert payload["assertion"]["passed"] is False
        assert payload["assertion"]["severity"] == AssertionSeverity.HARD.value

    def test_a_step_without_assertions_publishes_only_its_outcome(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        monitor.on_step_completed("job-1", "script-1", "neg", _step_result(StepStatus.PASSED))
        assert len(published) == 1


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------


class TestJobLifecycle:
    def test_a_failed_job_carries_why(self, monitor: ExecutionMonitor, published: list) -> None:
        monitor.on_job_failed("job-1", error="One or more scripts failed")
        _, payload = published[-1]
        assert payload["kind"] == EventKind.JOB_FAILED.value
        assert payload["error"] == "One or more scripts failed"

    @pytest.mark.parametrize(
        ("publish", "expected"),
        [
            (lambda m: m.on_job_completed("job-1"), "job.completed"),
            (lambda m: m.on_job_failed("job-1"), "job.failed"),
            (lambda m: m.on_job_cancelled("job-1"), "job.cancelled"),
        ],
    )
    def test_the_terminal_kinds_are_the_ones_that_close_the_stream(
        self,
        monitor: ExecutionMonitor,
        published: list,
        publish: Any,
        expected: str,
    ) -> None:
        publish(monitor)
        assert published[-1][0] == expected
        assert expected in TERMINAL_EVENTS

    def test_pausing_and_resuming_are_reported(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        monitor.on_job_paused("job-1")
        monitor.on_job_resumed("job-1")
        assert [event for event, _ in published] == ["job.paused", "job.resumed"]


class TestScriptLifecycle:
    def test_a_script_reports_its_outcome_in_its_result(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        """There is no script_failed kind — the result already carries status."""
        monitor.on_script_completed("job-1", ScriptResult(script_name="s", status="FAILED"))
        _, payload = published[-1]
        assert payload["kind"] == EventKind.SCRIPT_COMPLETED.value
        assert payload["result"]["status"] == "FAILED"


# ---------------------------------------------------------------------------
# The contract page
# ---------------------------------------------------------------------------


class TestContractPage:
    def test_every_kind_is_documented(self) -> None:
        """A kind the engine emits but the page omits is one consumers guess at."""
        page = _CONTRACT_PAGE.read_text(encoding="utf-8")
        undocumented = [kind.value for kind in EventKind if f"`{kind.value}`" not in page]
        assert undocumented == []


# ---------------------------------------------------------------------------
# A step whose `if:` says no must not run
# ---------------------------------------------------------------------------


class TestConditionalSkip:
    @pytest.mark.asyncio
    async def test_a_false_condition_skips_the_step_instead_of_running_it(
        self, monitor: ExecutionMonitor, published: list, mock_context: MagicMock
    ) -> None:
        """Recording SKIPPED and executing anyway is the one outcome `if:` rules out."""
        from tractusx_testlab.models.primitives.enums import StepPhase
        from tractusx_testlab.player.execution.phase import (
            FailurePolicy,
            PhaseConfig,
            run_phase,
        )

        script = MagicMock()
        script.definition.id = "script-1"
        script.definition.execution = [
            StepDefinition(
                id="never_runs",
                uses="util/log",
                with_={"message": "hi"},
                if_condition="${{ failure() }}",
            )
        ]
        script.definition.dataspace = None

        results, _ = await run_phase(
            script,
            mock_context,
            "job-1",
            monitor,
            None,
            PhaseConfig(
                phase=StepPhase.EXECUTION,
                phase_label="main",
                failure_policy=FailurePolicy.CONTINUE,
                evaluate_conditions=True,
                use_pause_gate=False,
                store_outputs=False,
            ),
        )

        assert [result.status for result in results] == [StepStatus.SKIPPED]
        assert [event for event, _ in published] == ["step.started", "step.skipped"]


# ---------------------------------------------------------------------------
# What the step is about to be given
# ---------------------------------------------------------------------------


def _encode_phase() -> Any:
    """A one-step phase whose ``with:`` reads a variable the run seeded."""
    from tractusx_testlab.models.primitives.enums import StepPhase
    from tractusx_testlab.player.execution.phase import FailurePolicy, PhaseConfig

    script = MagicMock()
    script.definition.id = "script-1"
    script.definition.dataspace = None
    script.dataspace_version = None
    script.definition.execution = [
        StepDefinition(
            id="encode",
            uses="util/base64",
            with_={"input": "${{ env.usage_policy }}", "url_safe": True},
        )
    ]
    config = PhaseConfig(
        phase=StepPhase.EXECUTION,
        phase_label="execution",
        failure_policy=FailurePolicy.CONTINUE,
        evaluate_conditions=True,
        use_pause_gate=False,
        store_outputs=False,
    )
    return script, config


class TestStepStartedReportsResolvedInputs:
    """``step_started.inputs`` says what the step gets, not what names it."""

    @pytest.mark.asyncio
    async def test_references_are_substituted_before_the_event_is_published(
        self, monitor: ExecutionMonitor, published: list, mock_context: MagicMock
    ) -> None:
        from tractusx_testlab.player.execution.phase import run_phase

        mock_context.set_variable("usage_policy", '{"permission": []}')
        script, config = _encode_phase()

        await run_phase(script, mock_context, "job-1", monitor, None, config)

        started = next(payload for event, payload in published if event == "step.started")
        assert started["inputs"] == {"input": '{"permission": []}', "url_safe": True}

    @pytest.mark.asyncio
    async def test_a_reference_naming_nothing_is_published_as_written_and_fails_the_step(
        self, monitor: ExecutionMonitor, published: list, mock_context: MagicMock
    ) -> None:
        """Nothing resolved it, so there is nothing else to show — and the step fails."""
        from tractusx_testlab.player.execution.phase import run_phase

        script, config = _encode_phase()

        results, _ = await run_phase(script, mock_context, "job-1", monitor, None, config)

        started = next(payload for event, payload in published if event == "step.started")
        assert started["inputs"] == {"input": "${{ env.usage_policy }}", "url_safe": True}
        assert [result.status for result in results] == [StepStatus.FAILED]
        assert "env.usage_policy" in (results[0].error or "")


# ---------------------------------------------------------------------------
# What is written down
# ---------------------------------------------------------------------------


def _step_with_a_credential() -> StepResult:
    """A step naming its own subject, built from the token it was told to send."""
    return StepResult(
        step_name="[1/1] pull",
        step_type="connector/consumer/dataplane_call",
        status=StepStatus.PASSED,
        request=HttpRequest(
            method="GET",
            url="https://sut.example/data",
            headers={"Authorization": "Bearer EDR-TOKEN", "Accept": "application/json"},
        ),
        response=HttpResponse(status_code=200, headers={"Set-Cookie": "session=abc"}),
    )


class TestCredentialsAreNotPublished:
    """The tracer redacts what it records; a step's own summary is redacted here.

    The step builds ``request``/``response`` out of what it was handed — the EDR
    token included — and that is the exchange a reader looks at first, so it
    reaches the transcript, the stream and the trace unless it is masked.
    """

    def test_a_step_event_does_not_carry_the_token_the_step_sent(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        monitor.on_step_completed("job-1", "script-1", "pull", _step_with_a_credential())

        [(_, payload)] = published
        headers = payload["result"]["request"]["headers"]
        assert headers["Authorization"] == "***"
        assert headers["Accept"] == "application/json"
        assert payload["result"]["response"]["headers"]["Set-Cookie"] == "***"

    def test_the_run_keeps_the_headers_a_script_may_name(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        """``returns: {response_headers: ...}`` reads what the SUT sent."""
        result = _step_with_a_credential()
        monitor.on_step_completed("job-1", "script-1", "pull", result)

        assert result.request.headers["Authorization"] == "Bearer EDR-TOKEN"

    def test_a_script_event_does_not_carry_it_either(
        self, monitor: ExecutionMonitor, published: list
    ) -> None:
        """The script event repeats every step it ran, wire included."""
        script = ScriptResult(script_id="script-1", execution=[_step_with_a_credential()])
        monitor.on_script_completed("job-1", script)

        [(_, payload)] = published
        step = payload["result"]["execution"][0]
        assert step["request"]["headers"]["Authorization"] == "***"

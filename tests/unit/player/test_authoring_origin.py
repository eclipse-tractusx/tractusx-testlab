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

"""A mistake in the TCK is not a failure of the system under test.

``AuthoringError`` — the TCK or the run's configuration is wrong, nothing was
tested — inherited ``origin: "sut"`` from ``TestLabError``. An asset id the TCK
reused across runs (the engine connector answered 409) reached the trace as a
failure of the SUT. These hold ``authoring`` apart from the verdict, and the two
cases that are not the author's: a value the SUT's call did not carry, and a
reference that only follows from a step that failed before it — which carries
that failure's origin, whoever's it was. Whether a step failed is what the
runner recorded, not what it published: a step with no ``returns:`` publishes
nothing and passed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tractusx_testlab.cli._run_summary import _test_failures
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import (
    AuthoringError,
    InfrastructureError,
    Job,
    MissingBindingError,
    MissingInputVariableError,
    SkipNotAllowedError,
    StandardConflictError,
    StepConfigError,
    UnknownBindingKeyError,
    UnresolvedReferenceError,
    VariableTypeError,
)
from tractusx_testlab.models.authoring.definitions import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus, TestStatus
from tractusx_testlab.models.runtime.results import ENGINE_FAULT_PREFIX, StepResult, TestResult
from tractusx_testlab.player.execution._trace_events import step_data
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.phase import EXECUTION, SETUP, TEARDOWN, run_phase
from tractusx_testlab.player.execution.step_runner import run_step, run_test
from tractusx_testlab.player.loading.resolver import TemplateDepthError, origin_of, resolve_params
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.http.request import HttpRequestStep
from tractusx_testlab.syntax import call_scope

#: What the engine connector's 409 was reported as, in the run that prompted this.
ALREADY_EXISTS = (
    "Asset 'testlab-ccmapi' already exists on the engine connector, and the connector "
    "keeps it as it was."
)


def _definition(url: str = "https://api.example.test/parts") -> StepDefinition:
    return StepDefinition(uses="http/http_request", name="fetch", with_={"url": url})


def _failed_with(error: Exception) -> StepResult:
    return StepResult(
        step_name="s",
        step_type="x",
        status=StepStatus.FAILED,
        error=str(error),
        error_code=getattr(error, "code", None),
        error_origin=getattr(error, "origin", None),
    )


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=ServiceManager(), job=Job(job_id="run-1"), config=TestlabConfig())


class TestTheClassSaysWhoseItIs:
    @pytest.mark.parametrize(
        "error",
        [
            AuthoringError(ALREADY_EXISTS),
            StepConfigError("http/http_request", "no url"),
            SkipNotAllowedError(["t1"]),
            UnresolvedReferenceError("env.bpn", ["env.bpnl"]),
            VariableTypeError("policy", "object", "is not a mapping"),
            TemplateDepthError("env.loop"),
        ],
        ids=lambda error: type(error).__name__,
    )
    def test_an_authoring_error_is_the_authors(self, error: AuthoringError) -> None:
        assert error.origin == "authoring"
        assert error.code == "AUTHORING_ERROR"

    @pytest.mark.parametrize(
        "error",
        [
            InfrastructureError("no engine connector is bound"),
            UnknownBindingKeyError("sut.conector.dsp_url", ["sut.connector.dsp_url"]),
            MissingBindingError([("sut", "connector", ["sut.connector.dsp_url"])]),
            MissingInputVariableError({"bpn": "the SUT's BPNL"}),
            StandardConflictError([("sut", "connector", "release", "a", "b")]),
        ],
        ids=lambda error: type(error).__name__,
    )
    def test_a_binding_that_does_not_add_up_is_the_deployments(
        self, error: InfrastructureError
    ) -> None:
        """Its code agrees with its origin rather than inheriting ``AUTHORING_ERROR``."""
        assert error.origin == "infrastructure"
        assert error.code == "INFRASTRUCTURE_ERROR"

    def test_a_reference_can_be_given_another_origin_where_it_is_raised(self) -> None:
        """And then is not named an authoring error: ``STEP_FAILED`` goes with ``sut``."""
        error = UnresolvedReferenceError("*.request.body.id", origin="sut")
        assert (error.origin, error.code) == ("sut", None)
        assert step_data(_failed_with(error))["errors"][0]["code"] == "STEP_FAILED"


class TestAReferenceThatResolvesToNothing:
    """What the resolver reads off the run, not off what a step published."""

    @pytest.fixture()
    def run(self, context: StepContext) -> StepContext:
        context.bind_step_namespace("execution")
        return context

    def test_an_undeclared_variable_is_the_authors(self, run: StepContext) -> None:
        run.set_variable("bpnl", "BPNL1")
        assert origin_of("env.bpn", run) == "authoring"

    def test_a_binding_is_the_authors(self, run: StepContext) -> None:
        assert origin_of("infrastructure.sut.connector.dsp", run) == "authoring"

    def test_a_name_a_step_did_not_publish_beside_ones_it_did_is_the_authors(
        self, run: StepContext
    ) -> None:
        """The step ran and published; the name is not one of its ``returns:``."""
        run.set_variable("execution.fetch.endpoint", "https://x")
        assert origin_of("execution.fetch.edr", run) == "authoring"

    def test_a_path_into_a_published_value_is_the_authors(self, run: StepContext) -> None:
        run.set_variable("execution.fetch.response_body", {})
        assert origin_of("execution.fetch.response_body.kind", run) == "authoring"

    def test_a_name_of_a_failed_step_that_published_others_is_the_authors(
        self, run: StepContext
    ) -> None:
        """A failed check still publishes: the name is still not one it declares."""
        run.steps.record(run.step_namespace, "fetch", StepStatus.FAILED, "sut")
        run.set_variable("execution.fetch.endpoint", "https://x")
        assert origin_of("execution.fetch.edr", run) == "authoring"

    @pytest.mark.parametrize("status", [StepStatus.PASSED, StepStatus.SKIPPED])
    def test_an_output_of_a_step_that_did_not_fail_is_the_authors(
        self, run: StepContext, status: StepStatus
    ) -> None:
        """No ``returns:``, or an ``if:`` that said no: nothing published, nothing failed."""
        run.steps.record(run.step_namespace, "fetch", status)
        assert origin_of("execution.fetch.endpoint", run) == "authoring"

    @pytest.mark.parametrize("origin", ["sut", "authoring", "infrastructure", "connector"])
    def test_an_output_of_a_step_that_failed_carries_its_origin(
        self, run: StepContext, origin: str
    ) -> None:
        run.steps.record(run.step_namespace, "fetch", StepStatus.FAILED, origin)
        assert origin_of("execution.fetch.endpoint", run) == origin

    @pytest.mark.parametrize("stopped_by", ["authoring", "sut"])
    def test_an_output_of_a_step_that_never_ran_follows_from_what_stopped_the_test(
        self, run: StepContext, stopped_by: str
    ) -> None:
        run.steps.record_stop(stopped_by)
        assert origin_of("setup.contract.contract_definition_id", run) == stopped_by

    def test_an_output_of_a_step_that_never_ran_and_nothing_stopped_is_the_authors(
        self, run: StepContext
    ) -> None:
        """A ``flow/if`` branch not taken, say: nothing failed for it to follow from."""
        assert origin_of("execution.fetch.endpoint", run) == "authoring"

    def test_what_the_sut_did_not_send_to_a_mock_is_the_suts(self, run: StepContext) -> None:
        run.set_variable("*.request.body", {})
        assert origin_of("*.request.body.messageId", run) == "sut"

    def test_a_name_a_mock_step_does_not_publish_is_the_authors(self, run: StepContext) -> None:
        """``*.process.<id>`` is checked at its root, like a phase's step outputs."""
        run.bind_step_namespace(call_scope.PROCESS)
        run.steps.record(run.step_namespace, "answer", StepStatus.PASSED)
        run.set_variable("*.process.answer.value", 1)
        assert origin_of("*.process.answer.valeu", run) == "authoring"
        assert origin_of("*.process.other.value", run) == "authoring"

    def test_another_call_scoped_name_is_the_authors(self, run: StepContext) -> None:
        assert origin_of("*.requests.body", run) == "authoring"

    def test_the_resolver_raises_with_the_origin_and_its_code(self, run: StepContext) -> None:
        run.steps.record_stop("authoring")
        with pytest.raises(UnresolvedReferenceError) as follow_on:
            resolve_params({"url": "${{ setup.contract.id }}"}, run)
        run.steps.record(run.step_namespace, "fetch", StepStatus.FAILED, "connector")
        with pytest.raises(UnresolvedReferenceError) as after_exchange:
            resolve_params({"url": "${{ execution.fetch.edr }}"}, run)
        run.steps.record(run.step_namespace, "query", StepStatus.FAILED, "sut")
        with pytest.raises(UnresolvedReferenceError) as verdict:
            resolve_params({"url": "${{ execution.query.id }}"}, run)

        assert (follow_on.value.origin, follow_on.value.code) == ("authoring", "AUTHORING_ERROR")
        assert (after_exchange.value.origin, after_exchange.value.code) == (
            "connector",
            "CONNECTOR_ERROR",
        )
        assert (verdict.value.origin, verdict.value.code) == ("sut", None)


def _phase_test(**phases: list[StepDefinition]) -> MagicMock:
    test = MagicMock()
    test.definition.id = "t"
    test.definition.cac = None
    test.dataspace_version = None
    for phase in ("setup", "execution", "teardown"):
        setattr(test.definition, phase, phases.get(phase, []))
    return test


def _log(step_id: str, value: str, **extra: object) -> StepDefinition:
    return StepDefinition(
        id=step_id, uses="util/log", with_={"message": "m", "value": value}, **extra
    )


class TestWhatAPhaseRecords:
    """The run, end to end: the outcome each step had is what a reference to it reads."""

    async def test_a_step_without_returns_that_passed_is_referenced_by_mistake(
        self, context: StepContext
    ) -> None:
        """It publishes nothing and failed nothing: the reference is the TCK's to fix."""
        context.steps.clear()
        test = _phase_test(
            execution=[_log("fetch", "x"), _log("read", "${{ execution.fetch.value }}")]
        )

        results, _ = await run_phase(test, context, "job-1", MagicMock(), None, EXECUTION)

        fetch, read = results
        assert fetch.status == StepStatus.PASSED
        assert (read.error_code, read.error_origin) == ("AUTHORING_ERROR", "authoring")

    async def test_a_step_its_if_skipped_is_referenced_by_mistake(
        self, context: StepContext
    ) -> None:
        context.steps.clear()
        test = _phase_test(
            execution=[
                _log(
                    "fetch",
                    "x",
                    if_condition="${{ failure() }}",
                    returns={"value": {"type": "string"}},
                ),
                _log("read", "${{ execution.fetch.value }}"),
            ]
        )

        results, _ = await run_phase(test, context, "job-1", MagicMock(), None, EXECUTION)

        assert results[0].status == StepStatus.SKIPPED
        assert (results[1].error_code, results[1].error_origin) == (
            "AUTHORING_ERROR",
            "authoring",
        )

    async def test_a_teardown_after_an_authoring_error_in_setup_is_the_authors_too(
        self, context: StepContext
    ) -> None:
        """CX-0135: the 409 stops setup, and teardown withdraws what never was created."""
        context.steps.clear()
        test = _phase_test(
            setup=[
                StepDefinition(
                    id="offer", uses="http/http_request", with_={"url": "https://x.test"}
                ),
                _log("contract", "c", returns={"value": {"type": "string"}}),
            ],
            teardown=[_log("withdraw", "${{ setup.contract.value }}")],
        )

        with patch.object(
            HttpRequestStep,
            "invoke",
            new_callable=AsyncMock,
            side_effect=AuthoringError(ALREADY_EXISTS),
        ):
            setup, _ = await run_phase(test, context, "job-1", MagicMock(), None, SETUP)
        teardown, _ = await run_phase(test, context, "job-1", MagicMock(), None, TEARDOWN)

        assert [result.status for result in setup] == [StepStatus.FAILED]
        (withdraw,) = teardown
        assert withdraw.status == StepStatus.FAILED
        assert (withdraw.error_code, withdraw.error_origin) == ("AUTHORING_ERROR", "authoring")
        assert step_data(withdraw)["errors"][0]["origin"] == "authoring"

    async def test_an_output_of_a_step_that_raised_follows_from_its_failure(
        self, context: StepContext
    ) -> None:
        context.steps.clear()
        test = _phase_test(
            setup=[
                StepDefinition(
                    id="offer",
                    uses="http/http_request",
                    with_={"url": "https://x.test"},
                    returns={"body": {"type": "object"}},
                )
            ],
            teardown=[_log("withdraw", "${{ setup.offer.body }}")],
        )

        with patch.object(
            HttpRequestStep, "invoke", new_callable=AsyncMock, side_effect=ValueError("bad reply")
        ):
            await run_phase(test, context, "job-1", MagicMock(), None, SETUP)
        (withdraw,), _ = await run_phase(test, context, "job-1", MagicMock(), None, TEARDOWN)

        assert (withdraw.error_code, withdraw.error_origin) == (None, "sut")

    async def test_a_step_in_the_branch_not_taken_is_referenced_by_mistake(
        self, context: StepContext
    ) -> None:
        """Even after a failure of the SUT stopped the test: the branch was skipped."""
        context.steps.clear()
        test = _phase_test(
            execution=[
                StepDefinition(
                    id="branch",
                    uses="flow/if",
                    with_={
                        "conditions": [{"input": 1, "operator": "not_null"}],
                        "then": [{"id": "taken", "uses": "util/log", "with": {"message": "m"}}],
                        "else": [
                            {
                                "id": "other",
                                "uses": "util/log",
                                "with": {"message": "m", "value": "v"},
                                "returns": {"value": {"type": "string"}},
                            }
                        ],
                    },
                ),
                StepDefinition(id="ask", uses="http/http_request", with_={"url": "https://x.test"}),
            ],
            teardown=[_log("clean", "${{ execution.other.value }}")],
        )

        with patch.object(
            HttpRequestStep, "invoke", new_callable=AsyncMock, side_effect=ValueError("no reply")
        ):
            execution, _ = await run_phase(test, context, "job-1", MagicMock(), None, EXECUTION)
        (clean,), _ = await run_phase(test, context, "job-1", MagicMock(), None, TEARDOWN)

        assert [result.status for result in execution] == [StepStatus.PASSED, StepStatus.FAILED]
        assert context.steps.stopped_by == "sut"
        assert (clean.error_code, clean.error_origin) == ("AUTHORING_ERROR", "authoring")

    async def test_a_new_test_forgets_the_last_ones_steps(self, context: StepContext) -> None:
        context.bind_step_namespace("setup")
        context.steps.record(context.step_namespace, "contract", StepStatus.FAILED, "sut")
        context.steps.record_stop("sut")

        test = _phase_test()
        test.name, test.dataspace_version = "t", "saturn"

        await run_test(test, context, "job-1", MagicMock(), MagicMock())

        assert context.steps.outcome_of("setup.contract") is None
        assert context.steps.stopped_by is None


class TestWhatTheRunnerRecords:
    async def test_an_authoring_error_is_recorded_as_the_authors(
        self, mock_context: MagicMock
    ) -> None:
        with patch.object(
            HttpRequestStep,
            "invoke",
            new_callable=AsyncMock,
            side_effect=AuthoringError(ALREADY_EXISTS),
        ):
            result = await run_step(HttpRequestStep, _definition(), "offer", mock_context)

        assert result.status == StepStatus.FAILED
        assert result.error == ALREADY_EXISTS
        assert not result.error.startswith(ENGINE_FAULT_PREFIX)
        assert result.error_code == "AUTHORING_ERROR"
        assert result.error_origin == "authoring"

    async def test_an_unresolved_reference_is_recorded_with_its_origin(
        self, mock_context: MagicMock
    ) -> None:
        mock_context.steps.record("setup", "offer", StepStatus.FAILED, "sut")
        typo = await run_step(HttpRequestStep, _definition("${{ env.bpn }}"), "s", mock_context)
        follow_on = await run_step(
            HttpRequestStep, _definition("${{ setup.offer.asset_id }}"), "s", mock_context
        )

        assert (typo.error_code, typo.error_origin) == ("AUTHORING_ERROR", "authoring")
        assert (follow_on.error_code, follow_on.error_origin) == (None, "sut")


class TestWhatAReaderSees:
    def _failed(self) -> StepResult:
        return StepResult(
            step_name="offer_mock",
            step_type="connector/provider/create_mock_asset",
            status=StepStatus.FAILED,
            error=ALREADY_EXISTS,
            error_code="AUTHORING_ERROR",
            error_origin="authoring",
        )

    def test_the_trace_publishes_the_origin(self) -> None:
        (error,) = step_data(self._failed())["errors"]
        assert error["origin"] == "authoring"
        assert error["code"] == "AUTHORING_ERROR"
        assert error["message"] == ALREADY_EXISTS

    def test_the_run_summary_says_where_to_fix_it(self) -> None:
        test = TestResult(
            test_id="t", test_name="t", status=TestStatus.FAILED, execution=[self._failed()]
        )
        lines = _test_failures(test)

        assert "           Fix in: the TCK or the run's configuration — nothing was tested" in lines

    def test_a_verdict_about_the_sut_needs_no_note(self) -> None:
        verdict = self._failed().model_copy(update={"error_origin": "sut", "error_code": None})
        test = TestResult(test_id="t", test_name="t", status=TestStatus.FAILED, execution=[verdict])

        assert not any("Fix in:" in line for line in _test_failures(test))

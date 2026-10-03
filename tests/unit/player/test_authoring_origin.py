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
cases that still are the SUT's: a value the SUT's call did not carry, and a
reference that only follows from a step that failed before it.
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
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.player.loading.resolver import TemplateDepthError, origin_of, resolve_params
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.http.request import HttpRequestStep

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
    def test_an_undeclared_variable_is_the_authors(self) -> None:
        assert origin_of("env.bpn", ["bpnl"]) == "authoring"

    def test_a_binding_is_the_authors(self) -> None:
        assert origin_of("infrastructure.sut.connector.dsp", []) == "authoring"

    def test_a_name_a_step_did_not_publish_beside_ones_it_did_is_the_authors(self) -> None:
        """The step ran and published; the name is not one of its ``returns:``."""
        assert origin_of("execution.fetch.edr", ["execution.fetch.endpoint"]) == "authoring"

    def test_a_path_into_a_published_value_is_the_authors(self) -> None:
        in_scope = ["execution.fetch.response_body"]
        assert origin_of("execution.fetch.response_body.kind", in_scope) == "authoring"

    @pytest.mark.parametrize("namespace", ["setup", "execution", "teardown"])
    def test_an_output_of_a_step_that_published_nothing_follows_from_its_failure(
        self, namespace: str
    ) -> None:
        """The step that failed carries the origin; this one is not a TCK mistake."""
        in_scope = ["execution.id", "execution.other.value"]
        assert origin_of(f"{namespace}.fetch.endpoint", in_scope) == "sut"

    def test_what_the_sut_did_not_send_to_a_mock_is_the_suts(self) -> None:
        assert origin_of("*.request.body.messageId", ["*.request.body"]) == "sut"

    def test_the_resolver_raises_with_the_origin(self, context: StepContext) -> None:
        context.set_variable("execution.other.value", 1)
        with pytest.raises(UnresolvedReferenceError) as follow_on:
            resolve_params({"url": "${{ execution.fetch.endpoint }}"}, context)
        with pytest.raises(UnresolvedReferenceError) as typo:
            resolve_params({"url": "${{ env.bpn }}"}, context)

        assert follow_on.value.origin == "sut"
        assert typo.value.origin == "authoring"


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

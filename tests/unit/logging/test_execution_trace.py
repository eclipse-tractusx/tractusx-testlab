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

"""What ADR-0016 promises a reader of an execution trace.

These hold the trace to the three things it is read for: that an event says
where it belongs without the reader tracking state, that a step's result is
self-contained, and that the wire is in it — especially for the step that
failed, which is the only reason anyone opens the file.
"""

from __future__ import annotations

import io
import json

from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.models.primitives.enums import StepPhase, StepStatus
from tractusx_testlab.models.runtime.results import (
    ENGINE_FAULT_PREFIX,
    AssertionResult,
    HttpExchange,
    HttpRequest,
    HttpResponse,
    StepResult,
)
from tractusx_testlab.player.execution._trace_events import call_data, step_data, validation_of
from tractusx_testlab.player.execution.monitor import ExecutionMonitor


def _read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class TestEnvelope:
    def test_every_line_is_a_cloudevent(self, tmp_path) -> None:
        trace = ExecutionTrace.for_job("demo-tck", "job1", tmp_path)
        trace.emit("tck.start", {"tck_id": "demo-tck"})
        trace.close()

        (event,) = _read(trace.path)
        assert event["specversion"] == "1.0"
        assert event["type"] == "tck.start"
        assert event["source"] == "testlab/player/lifecycle"
        assert event["time"].endswith("Z")

    def test_the_sequence_counts_the_whole_run(self, tmp_path) -> None:
        """One counter for the run — it is what an SSE reconnect resumes from."""
        trace = ExecutionTrace.for_job("demo-tck", "job1", tmp_path)
        for _ in range(3):
            trace.emit("tck.test.start", {"test_id": "t"}, scope=("t",))
        trace.close()

        assert [event["sequence"] for event in _read(trace.path)] == [1, 2, 3]

    def test_the_id_names_the_phase_between_the_test_and_the_step(self, tmp_path) -> None:
        """A step id is unique only within its phase, so the path carries it.

        Without the segment a ``cleanup_asset`` in teardown and one in setup
        share a path and are told apart only by the payload hash.
        """
        trace = ExecutionTrace.for_job("demo-tck", "job1", tmp_path)
        trace.emit("tck.test.step.passed", {"attempt": 1}, scope=("my-test", "teardown", "cleanup"))
        trace.close()

        (event,) = _read(trace.path)
        assert event["id"].startswith("demo-tck/my-test/teardown/cleanup/tck.test.step.passed/")

    def test_the_same_payload_gets_the_same_id(self, tmp_path) -> None:
        """The trace is an audit record; an id that changes per read is not one."""
        trace = ExecutionTrace.for_job("demo-tck", "job1", tmp_path)
        first = trace.emit("tck.test.start", {"test_id": "t"}, scope=("t",))
        second = trace.emit("tck.test.start", {"test_id": "t"}, scope=("t",))
        trace.close()

        assert first["id"] == second["id"]

    def test_a_trace_with_nowhere_to_write_still_counts(self, tmp_path) -> None:
        trace = ExecutionTrace("demo-tck")
        assert trace.path is None
        assert trace.emit("tck.start", {})["sequence"] == 1


def _assertion_result(passed: bool) -> AssertionResult:
    return AssertionResult(
        assertion=Assertion(uses="validate/assert", with_={"input": "value", "operator": "equals"}),
        passed=passed,
        expected=200,
        actual=200 if passed else 403,
        message="" if passed else "expected 200, got 403",
    )


class TestStepData:
    def test_checks_are_nested_not_separate_events(self) -> None:
        result = StepResult(
            step_name="s",
            step_type="http/http_request",
            status=StepStatus.PASSED,
            assertions=[_assertion_result(True)],
        )
        (validation,) = step_data(result)["validations"]
        assert validation["field"] == "value"
        assert validation["inputs"] == {"assertion": "equals", "expected": 200}
        assert validation["outputs"] == {"actual": 200, "passed": True}

    def test_a_failed_check_says_why(self) -> None:
        validation = validation_of(_assertion_result(False))
        assert validation["errors"][0]["message"] == "expected 200, got 403"

    def test_what_went_in_and_what_came_out(self) -> None:
        """The pair a reader compares: what the step was given, what it published."""
        result = StepResult(
            step_name="s",
            step_type="connector/consumer/query_catalog",
            status=StepStatus.PASSED,
            inputs={"counter_party_id": "BPNL000000000001"},
            output={"datasets": []},
        )
        data = step_data(result)
        assert data["inputs"] == {"counter_party_id": "BPNL000000000001"}
        assert data["outputs"] == {"datasets": []}

    def test_the_wire_is_not_repeated_in_the_terminal_event(self) -> None:
        """Every call was already published as it happened, in the same stream."""
        result = StepResult(
            step_name="s",
            step_type="http/http_request",
            status=StepStatus.PASSED,
            request=HttpRequest(method="GET", url="https://sut.example/x"),
            response=HttpResponse(status_code=200),
            exchanges=[
                HttpExchange(
                    request=HttpRequest(method="GET", url="https://sut.example/x"),
                    response=HttpResponse(status_code=200),
                )
            ],
        )
        data = step_data(result)
        assert "request" not in data
        assert "response" not in data
        assert "exchanges" not in data

    def test_a_call_names_what_was_sent_and_who_sent_it(self) -> None:
        call = HttpExchange(
            request=HttpRequest(method="POST", url="https://sut.example/catalog/request"),
            response=HttpResponse(status_code=403),
            context="CatalogController.get_catalog",
        )
        data = call_data(2, call)
        assert data["index"] == 2
        assert data["context"] == "CatalogController.get_catalog"
        assert data["request"].url == "https://sut.example/catalog/request"
        assert data["response"].status_code == 403

    def test_a_call_that_never_answered_says_so(self) -> None:
        call = HttpExchange(
            request=HttpRequest(method="GET", url="https://unreachable"),
            error="ConnectTimeout: timed out",
        )
        data = call_data(1, call)
        assert "response" not in data
        assert data["errors"][0]["message"] == "ConnectTimeout: timed out"

    def test_an_engine_fault_is_not_a_verdict_about_the_sut(self) -> None:
        """A red run needs to say whether to fix the SUT or file a TestLab bug."""
        engine = StepResult(
            step_name="s",
            step_type="x",
            status=StepStatus.FAILED,
            error=f"{ENGINE_FAULT_PREFIX}connector client blew up",
        )
        sut = StepResult(
            step_name="s",
            step_type="x",
            status=StepStatus.FAILED,
            error="the SUT said 403",
        )
        assert step_data(engine)["errors"][0]["origin"] == "engine"
        assert step_data(engine)["errors"][0]["message"] == "connector client blew up"
        assert step_data(sut)["errors"][0]["origin"] == "sut"

    def test_a_bare_output_is_published_under_the_name_it_is_read_by(self) -> None:
        """``util/base64`` publishes one value; the trace says which output it is."""
        result = StepResult(
            step_name="encode_filter",
            step_type="util/base64",
            status=StepStatus.PASSED,
            output="W3sibmFtZSI6ImRpZ2l0YWxUd2luVHlwZSJ9",
        )
        assert step_data(result)["outputs"] == {"value": "W3sibmFtZSI6ImRpZ2l0YWxUd2luVHlwZSJ9"}

    def test_named_outputs_keep_their_own_names(self) -> None:
        result = StepResult(
            step_name="pull_dtr",
            step_type="connector/consumer/pull_data_filtered",
            status=StepStatus.PASSED,
            output={"dataplane_url": "https://dataplane.example", "edr_token": "abc"},
        )
        assert step_data(result)["outputs"] == {
            "dataplane_url": "https://dataplane.example",
            "edr_token": "abc",
        }

    def test_a_step_that_produced_nothing_names_nothing(self) -> None:
        result = StepResult(step_name="s", step_type="x", status=StepStatus.PASSED, output=None)
        assert step_data(result)["outputs"] is None

    def test_a_failure_that_named_itself_keeps_its_name_and_its_evidence(self) -> None:
        """A comparison is rendered by the IDE, not parsed back out of a sentence."""
        result = StepResult(
            step_name="pull_dtr",
            step_type="connector/consumer/pull_data_filtered",
            status=StepStatus.FAILED,
            error="no offer is made under a policy this step accepts",
            error_code="POLICY_MISMATCH",
            error_context={"offers_compared": 2},
        )
        (error,) = step_data(result)["errors"]
        assert error["code"] == "POLICY_MISMATCH"
        assert error["origin"] == "sut"
        assert error["context"] == {"offers_compared": 2}

    def test_an_error_with_nothing_extra_to_say_carries_no_context(self) -> None:
        result = StepResult(
            step_name="s", step_type="x", status=StepStatus.FAILED, error="the SUT said 403"
        )
        (error,) = step_data(result)["errors"]
        assert error["code"] == "STEP_FAILED"
        assert "context" not in error

    def test_the_phase_survives_into_the_scope(self) -> None:
        result = StepResult(step_name="s", step_type="x", phase=StepPhase.TEARDOWN)
        assert result.phase.value.lower() == "teardown"


class TestTheTranscriptMeetsTheTrace:
    """The console line and the event are one lookup apart.

    A step is many calls, and on the console they were many identical lines:
    ``step.call [dtr-filterability]``, once per call, naming neither the step
    that was calling nor what it called. The line now carries the id of the
    event it was written from, which is what turns a transcript into an index
    of the trace.
    """

    @staticmethod
    def _run(tmp_path) -> tuple[ExecutionTrace, str]:
        stream = io.StringIO()
        trace = ExecutionTrace.for_job("demo-tck", "job1", tmp_path)
        # A logger of its own: ``logging`` hands out one object per name, and a
        # name shared with another test would collect that test's handlers too.
        monitor = ExecutionMonitor(
            StructuredLogger("testlab.test.transcript_meets_trace", stream=stream), trace
        )
        monitor.on_step_call(
            "job1",
            "dtr-filterability",
            "pull_dtr",
            "connector/consumer/pull_data_filtered",
            "execution",
            3,
            HttpExchange(
                request=HttpRequest(method="POST", url="https://edc/management/v3/catalog/request"),
                response=HttpResponse(status_code=200, duration_ms=1373.2),
                context="CatalogController.get_catalog",
            ),
        )
        trace.close()
        return trace, stream.getvalue()

    def test_the_id_on_the_line_is_the_id_of_the_written_event(self, tmp_path) -> None:
        trace, transcript = self._run(tmp_path)

        printed = transcript.rsplit(" id=", 1)[1].strip()
        (event,) = _read(trace.path)
        assert printed == event["id"]
        assert printed.endswith("/calls/3/tck.test.step.call/" + event["id"].rsplit("/", 1)[1])

    def test_the_line_says_which_call_of_which_step_it_was(self, tmp_path) -> None:
        _, transcript = self._run(tmp_path)

        assert "pull_dtr" in transcript
        assert "#3" in transcript
        assert "CatalogController.get_catalog" in transcript
        assert "POST https://edc/management/v3/catalog/request" in transcript

    def test_an_untraced_run_prints_the_line_without_an_id(self, tmp_path) -> None:
        """An embedder that wants only the transcript pays for nothing else."""
        stream = io.StringIO()
        monitor = ExecutionMonitor(StructuredLogger("testlab.test.untraced", stream=stream))
        monitor.on_job_started("job1", "demo-tck")

        assert "job.started" in stream.getvalue()
        assert " id=" not in stream.getvalue()

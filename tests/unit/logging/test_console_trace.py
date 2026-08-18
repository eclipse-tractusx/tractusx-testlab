################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.


"""What a person watching a run actually sees.

The JSONL carries every field of every event. The console line is a rendering
of the same data for someone reading it go by, and it used to render almost
none of it: `_build_inline_message` looked for flat ``status`` / ``duration_s``
/ ``request`` / ``response`` keys that the typed events never carried, so every
step and assertion printed as its bare event name and the script it was in.
"""

from __future__ import annotations

from tractusx_testlab.logging.console import render

_ASSERTION_PASSED = {
    "kind": "assertion_result",
    "script": "wiring",
    "step_id": "call",
    "step_name": "wiring[call]:http/http_request",
    "index": 1,
    "assertion": {
        "assertion": {
            "uses": "validate/assert",
            "with_": {"input": "status_code", "operator": "equals"},
        },
        "passed": True,
        "expected": 200,
        "actual": 200,
        "message": "",
        "severity": "HARD",
    },
}

_STEP_WITH_EXCHANGE = {
    "kind": "step_completed",
    "script": "wiring",
    "step_id": "call",
    "result": {
        "step_name": "wiring[call]:http/http_request",
        "step_type": "http/http_request",
        "status": "PASSED",
        "duration_s": 0.024,
        "request": {"method": "GET", "url": "http://sut/probe", "body": None},
        "response": {"status_code": 200, "body": {"kind": "probe"}, "duration_ms": 0.0},
    },
}


class TestAnAssertionLine:
    def test_it_says_which_check_and_how_it_went(self) -> None:
        line = render("assertion.result", _ASSERTION_PASSED)
        assert line.startswith("assert.pass")
        assert "equals(status_code)" in line
        assert "expected=200" in line
        assert "actual=200" in line

    def test_a_failure_is_findable_by_eye(self) -> None:
        failed = {
            **_ASSERTION_PASSED,
            "assertion": {
                **_ASSERTION_PASSED["assertion"],
                "passed": False,
                "actual": 503,
                "message": "expected 200, got 503",
            },
        }
        line = render("assertion.result", failed)
        assert line.startswith("assert.FAIL")
        assert "expected 200, got 503" in line

    def test_a_field_check_names_the_path_it_read(self) -> None:
        with_path = {
            **_ASSERTION_PASSED,
            "assertion": {
                **_ASSERTION_PASSED["assertion"],
                "assertion": {
                    "uses": "validate/field",
                    "with_": {"input": "body", "path": "kind", "operator": "equals"},
                },
            },
        }
        assert "equals(body.kind)" in render("assertion.result", with_path)

    def test_a_soft_assertion_says_so(self) -> None:
        soft = {
            **_ASSERTION_PASSED,
            "assertion": {**_ASSERTION_PASSED["assertion"], "severity": "SOFT"},
        }
        assert "(soft)" in render("assertion.result", soft)


class TestAStepOutcomeLine:
    def test_it_names_the_step_its_status_and_its_duration(self) -> None:
        line = render("step.completed", _STEP_WITH_EXCHANGE)
        assert "call" in line
        assert "http/http_request" in line
        assert "PASSED" in line
        assert "24ms" in line

    def test_the_request_and_the_response_are_shown(self) -> None:
        """A conformance verdict comes off the wire, so the wire is in the trace."""
        line = render("step.completed", _STEP_WITH_EXCHANGE)
        assert "→ GET http://sut/probe" in line
        assert "← 200" in line
        assert '{"kind": "probe"}' in line

    def test_an_unmeasured_duration_is_not_printed_as_zero(self) -> None:
        assert "in 0ms" not in render("step.completed", _STEP_WITH_EXCHANGE)

    def test_a_step_that_made_no_call_shows_no_exchange(self) -> None:
        quiet = {
            **_STEP_WITH_EXCHANGE,
            "result": {**_STEP_WITH_EXCHANGE["result"], "request": None, "response": None},
        }
        line = render("step.completed", quiet)
        assert "→" not in line and "←" not in line

    def test_a_failure_carries_its_reason(self) -> None:
        failed = {
            **_STEP_WITH_EXCHANGE,
            "kind": "step_failed",
            "result": {
                **_STEP_WITH_EXCHANGE["result"],
                "status": "FAILED",
                "error": "no EDR was issued",
            },
        }
        assert "no EDR was issued" in render("step.failed", failed)

    def test_a_long_body_is_clipped_with_the_cut_made_visible(self) -> None:
        big = {
            **_STEP_WITH_EXCHANGE,
            "result": {
                **_STEP_WITH_EXCHANGE["result"],
                "response": {"status_code": 200, "body": {"blob": "x" * 5000}},
            },
        }
        line = render("step.completed", big)
        assert "…(+" in line
        assert len(line) < 1000


class TestTheOtherLines:
    def test_a_started_step_names_itself_and_its_phase(self) -> None:
        line = render(
            "step.started",
            {
                "kind": "step_started",
                "script": "wiring",
                "step_id": "call",
                "step_type": "http/http_request",
                "phase": "execution",
            },
        )
        assert "call" in line and "http/http_request" in line and "(execution)" in line

    def test_a_finished_script_reports_its_check_tally(self) -> None:
        line = render(
            "script.completed",
            {
                "kind": "script_completed",
                "result": {
                    "script_name": "Wiring",
                    "status": "COMPLETED",
                    "assertion_summary": {"total": 4, "passed": 4},
                },
            },
        )
        assert "COMPLETED" in line and "4/4 checks passed" in line

    def test_an_event_with_nothing_to_add_renders_as_itself(self) -> None:
        assert render("job.started", {"kind": "job_started", "tck_id": "probe"}) == (
            "job.started [probe]"
        )

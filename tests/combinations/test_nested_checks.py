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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""A flow step reports what its sub-steps checked, each check under its sub-step.

``flow/if``, ``flow/retry`` and ``labs/flow/for_each`` run their sub-steps
through the same runner as a top-level step, but only the flow step has a
result of its own. The sub-steps' checks are that result's, tagged with the
path of sub-steps they were evaluated on — so a passing check is reported, a
failing one is named, and the summary counts both.
"""

from __future__ import annotations

from typing import Any

import pytest

from combinations.harness import Harness
from combinations.http_double import HttpDouble, Response
from tractusx_testlab.models import StepStatus
from tractusx_testlab.player.execution._trace_events import step_data

pytestmark = pytest.mark.asyncio


def _status_is(code: int, **extra: Any) -> dict:
    return {
        "uses": "validate/assert",
        "with": {"input": "status_code", "operator": "equals", "value": code, **extra},
    }


def _get(url: str, step_id: str, *checks: dict) -> dict:
    return {
        "id": step_id,
        "uses": "http/http_request",
        "with": {"method": "GET", "url": url},
        "validate": list(checks),
    }


def _if(step_id: str, holds: bool, then: list[dict], otherwise: list[dict] | None = None) -> dict:
    block: dict = {
        "id": step_id,
        "uses": "flow/if",
        "with": {
            "conditions": [{"input": "yes" if holds else None, "operator": "not_null"}],
            "then": then,
        },
    }
    if otherwise:
        block["with"]["else"] = otherwise
    return block


class TestABranch:
    async def test_the_checks_of_the_branch_taken_are_the_blocks(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/ok", {})
        base = http.start()

        outcome = await harness.run(
            _if(
                "branch",
                True,
                then=[_get(f"{base}/ok", "probe", _status_is(200), _status_is(200))],
                otherwise=[_get(f"{base}/ok", "never", _status_is(200))],
            )
        )

        result = outcome.result("branch")
        assert result.status is StepStatus.PASSED
        assert [check.step_path for check in result.assertions] == [["probe"], ["probe"]]
        assert all(check.passed for check in result.assertions)
        # The branch not taken declared nothing: it did not run.
        assert result.nested_declared == 2

    async def test_a_failing_check_in_the_branch_is_named_and_is_a_verdict(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route("GET", "/down", Response(status=503, body={}))
        base = http.start()

        outcome = await harness.run(
            _if("branch", True, then=[_get(f"{base}/down", "probe", _status_is(200))])
        )

        result = outcome.result("branch")
        assert result.status is StepStatus.FAILED
        [check] = result.assertions
        assert (check.step_path, check.passed, check.actual) == (["probe"], False, 503)
        # A check the SUT failed, not a bug in TestLab.
        assert result.error_origin == "sut"
        assert not (result.error or "").startswith("[engine fault]")
        assert "'then' branch: 'http/http_request'" in (result.error or "")

    async def test_a_soft_check_in_the_branch_warns_without_failing_it(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/ok", {})
        base = http.start()

        outcome = await harness.run(
            _if(
                "branch", True, then=[_get(f"{base}/ok", "probe", _status_is(201, severity="SOFT"))]
            )
        )

        result = outcome.result("branch")
        assert result.status is StepStatus.PASSED
        [check] = result.assertions
        assert not check.passed
        assert check.severity.value == "SOFT"

    async def test_the_trace_says_which_sub_step_a_check_ran_on(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/ok", {})
        base = http.start()

        outcome = await harness.run(
            _if("branch", True, then=[_get(f"{base}/ok", "probe", _status_is(200))])
        )

        [validation] = step_data(outcome.result("branch"))["validations"]
        assert validation["step"] == ["probe"]
        assert validation["outputs"] == {"actual": 200, "passed": True}

    async def test_a_branch_inside_a_branch_keeps_the_whole_path(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/ok", {})
        base = http.start()

        outcome = await harness.run(
            _if(
                "outer",
                True,
                then=[_if("inner", True, then=[_get(f"{base}/ok", "probe", _status_is(200))])],
            )
        )

        result = outcome.result("outer")
        assert [check.step_path for check in result.assertions] == [["inner", "probe"]]
        assert result.nested_declared == 1


class TestARetry:
    async def test_only_the_last_attempts_checks_are_reported(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """An attempt that failed and was retried is not a verdict."""
        http.route(
            "GET",
            "/eventually",
            Response(status=503, body={}),
            Response(status=200, body={}),
        )
        base = http.start()

        outcome = await harness.run(
            {
                "id": "await_ready",
                "uses": "flow/retry",
                "with": {
                    "max_attempts": 3,
                    "delay_s": 0,
                    "steps": [_get(f"{base}/eventually", "poll", _status_is(200))],
                },
            }
        )

        result = outcome.result("await_ready")
        assert result.status is StepStatus.PASSED
        [check] = result.assertions
        assert (check.step_path, check.passed) == (["poll"], True)


class TestALoop:
    async def test_every_items_checks_are_reported_under_the_item(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/a", {})
        http.json_route("GET", "/b", {})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "each",
                "uses": "labs/flow/for_each",
                "with": {
                    "items": ["a", "b"],
                    "steps": [_get(f"{base}/${{{{ each.item }}}}", "fetch", _status_is(200))],
                },
            }
        )

        result = outcome.result("each")
        assert result.status is StepStatus.PASSED, result.error
        assert [check.step_path for check in result.assertions] == [
            ["[0]", "fetch"],
            ["[1]", "fetch"],
        ]
        assert result.nested_declared == 2

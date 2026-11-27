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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Focus runs (``only_tests``) and ``on_failure: stop``, at the session that runs the tests."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from tractusx_testlab.authoring._inspection import build_inspection_result
from tractusx_testlab.authoring.test import Tck, Test
from tractusx_testlab.models.authoring.definitions import TckTestEntry
from tractusx_testlab.models.primitives.enums import TestStatus
from tractusx_testlab.models.primitives.exceptions import (
    SkipNotAllowedError,
    UnknownFocusTestError,
)
from tractusx_testlab.models.runtime.results import AssertionSummary, TestResult
from tractusx_testlab.player.execution import session as session_module
from tractusx_testlab.player.execution._plan import (
    NOT_SELECTED_REASON,
    STOPPED_REASON,
    TestPlan,
)
from tractusx_testlab.player.execution._skip import resolve_only_ids, resolve_plan
from tractusx_testlab.player.execution._trace_events import test_data as trace_test_data
from tractusx_testlab.player.execution._trace_formatter import make_intentionally_skipped_result
from tractusx_testlab.player.execution.session import TckSession

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _test(stem: str, *, skippable: bool = False, on_failure: str = "continue") -> Test:
    definition = MagicMock()
    definition.id = stem
    definition.metadata.name = stem.title()
    definition.dataspace = None
    definition.setup = definition.execution = definition.teardown = []
    return Test(definition, skippable=skippable, test_id=f"{stem}.yaml", on_failure=on_failure)


def _tck(*tests: Test) -> Tck:
    tck_def = MagicMock()
    tck_def.metadata.name = "Focus TCK"
    tck_def.env = None
    tck_def.tests = []
    tck = Tck(tck_def)
    tck._tests = list(tests)
    return tck


def _result(test: Test, status: TestStatus, error: str | None = None) -> TestResult:
    now = datetime.now(UTC)
    return TestResult(
        test_id=test.definition.id,
        test_name=test.name,
        status=status,
        started_at=now,
        finished_at=now,
        total_duration_s=0.0,
        assertion_summary=AssertionSummary(total=1, passed=0, failed_hard=1, failed_soft=0),
        error=error,
    )


def _session(tck: Tck, runtime_vars: dict | None = None) -> tuple[TckSession, MagicMock]:
    jobs = MagicMock()
    jobs.is_cancelled.return_value = False
    monitor = MagicMock()
    session = TckSession(
        tck=tck,
        job=MagicMock(job_id="job-1"),
        context=MagicMock(),
        monitor=monitor,
        jobs=jobs,
        services=MagicMock(),
        job_logger=MagicMock(),
        trace=None,
        plan=resolve_plan(tck, runtime_vars),
        records=contextlib.ExitStack(),
        on_close=lambda: None,
    )
    return session, jobs


class _Runs:
    """How each test ends (``planned``, COMPLETED otherwise) and which tests ran."""

    def __init__(self) -> None:
        self.planned: dict[str, tuple[TestStatus, str | None]] = {}
        self.ran: list[str] = []


@pytest.fixture
def outcomes(monkeypatch: pytest.MonkeyPatch) -> _Runs:
    """Stand in for ``run_test``: no step runs, each test ends as planned."""
    runs = _Runs()

    async def fake_run_test(test: Test, *_args: object) -> TestResult:
        runs.ran.append(test.test_id)
        status, error = runs.planned.get(test.test_id, (TestStatus.COMPLETED, None))
        return _result(test, status, error)

    monkeypatch.setattr(session_module, "run_test", fake_run_test)
    return runs


def _by_id(result) -> dict[str, TestResult]:
    return {test.test_id: test for test in result.tests}


# ---------------------------------------------------------------------------
# The manifest key
# ---------------------------------------------------------------------------


class TestOnFailureKey:
    def test_continue_is_the_default(self) -> None:
        assert TckTestEntry(id="a.yaml").on_failure == "continue"

    def test_stop_is_accepted(self) -> None:
        assert TckTestEntry(id="a.yaml", on_failure="stop").on_failure == "stop"

    def test_anything_else_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            TckTestEntry(id="a.yaml", on_failure="abort")

    def test_the_test_wrapper_carries_it(self) -> None:
        assert _test("a", on_failure="stop").on_failure == "stop"
        assert _test("b").on_failure == "continue"

    def test_inspection_exposes_it_next_to_skippable(self) -> None:
        tck = _tck(_test("a", on_failure="stop"), _test("b", skippable=True))
        report = build_inspection_result(tck)
        assert [(t.test_id, t.skippable, t.on_failure) for t in report.tests] == [
            ("a.yaml", False, "stop"),
            ("b.yaml", True, "continue"),
        ]


# ---------------------------------------------------------------------------
# on_failure: stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStopOnFailure:
    async def test_a_failed_stop_test_skips_every_later_test(self, outcomes) -> None:
        a, b, c = _test("a"), _test("b", on_failure="stop"), _test("c")
        outcomes.planned["b.yaml"] = (TestStatus.FAILED, None)
        session, jobs = _session(_tck(a, b, c))

        await session.run_all()
        result = await session.close()

        assert outcomes.ran == ["a.yaml", "b.yaml"]
        by_id = _by_id(result)
        assert by_id["c"].status == TestStatus.SKIPPED
        assert by_id["c"].skip_reason == "stopped: b.yaml failed and is marked on_failure: stop"
        assert by_id["a"].skip_reason is None
        assert result.status == TestStatus.FAILED
        jobs.fail.assert_called_once()

    async def test_an_engine_fault_stops_the_run_too(self, outcomes) -> None:
        """An error the engine raised (``[engine fault]``, the ERROR case) ends the test FAILED."""
        a, b = _test("a", on_failure="stop"), _test("b")
        outcomes.planned["a.yaml"] = (TestStatus.FAILED, "[engine fault] connector unreachable")
        session, _ = _session(_tck(a, b))

        await session.run_all()
        result = await session.close()

        assert outcomes.ran == ["a.yaml"]
        assert _by_id(result)["b"].skip_reason == STOPPED_REASON.format(test_id="a.yaml")
        assert result.status == TestStatus.FAILED

    async def test_a_passing_stop_test_stops_nothing(self, outcomes) -> None:
        a, b = _test("a", on_failure="stop"), _test("b")
        session, _ = _session(_tck(a, b))

        await session.run_all()
        result = await session.close()

        assert outcomes.ran == ["a.yaml", "b.yaml"]
        assert result.status == TestStatus.COMPLETED

    async def test_a_failed_continue_test_lets_the_run_go_on(self, outcomes) -> None:
        a, b = _test("a"), _test("b")
        outcomes.planned["a.yaml"] = (TestStatus.FAILED, None)
        session, _ = _session(_tck(a, b))

        await session.run_all()

        assert outcomes.ran == ["a.yaml", "b.yaml"]

    async def test_the_last_test_stopping_skips_nothing_and_fails(self, outcomes) -> None:
        a, b = _test("a"), _test("b", on_failure="stop")
        outcomes.planned["b.yaml"] = (TestStatus.FAILED, None)
        session, _ = _session(_tck(a, b))

        await session.run_all()
        result = await session.close()

        assert outcomes.ran == ["a.yaml", "b.yaml"]
        assert [t.status for t in result.tests] == [TestStatus.COMPLETED, TestStatus.FAILED]
        assert result.status == TestStatus.FAILED

    async def test_the_skipped_tests_are_announced_like_an_intentional_skip(self, outcomes) -> None:
        a, b = _test("a", on_failure="stop"), _test("b")
        outcomes.planned["a.yaml"] = (TestStatus.FAILED, None)
        session, _ = _session(_tck(a, b))
        monitor = session._monitor

        await session.run_all()

        monitor.on_test_started.assert_any_call("job-1", "b", 1, skipped=True)
        completed = [call.args[1] for call in monitor.on_test_completed.call_args_list]
        assert completed[-1].test_id == "b"
        assert completed[-1].status == TestStatus.SKIPPED

    async def test_a_test_already_left_out_by_skip_tests_keeps_its_own_skip(self, outcomes) -> None:
        a, b, c = _test("a", on_failure="stop"), _test("b", skippable=True), _test("c")
        outcomes.planned["a.yaml"] = (TestStatus.FAILED, None)
        session, _ = _session(_tck(a, b, c), {"skip_tests": ["b.yaml"]})

        await session.run_all()
        result = await session.close()

        by_id = _by_id(result)
        assert by_id["b"].skip_reason is None
        assert by_id["c"].skip_reason == STOPPED_REASON.format(test_id="a.yaml")


# ---------------------------------------------------------------------------
# only_tests (focus runs)
# ---------------------------------------------------------------------------


class TestResolveOnlyIds:
    def test_a_list(self) -> None:
        tck = _tck(_test("a"), _test("b"))
        assert resolve_only_ids(tck, {"only_tests": ["b.yaml"]}) == {"b.yaml"}

    def test_a_comma_separated_string(self) -> None:
        tck = _tck(_test("a"), _test("b"), _test("c"))
        assert resolve_only_ids(tck, {"only_tests": "a.yaml, c.yaml"}) == {"a.yaml", "c.yaml"}

    def test_empty_is_a_plain_run(self) -> None:
        tck = _tck(_test("a"))
        assert resolve_only_ids(tck, {"only_tests": []}) == frozenset()
        assert resolve_only_ids(tck, None) == frozenset()

    def test_an_unknown_id_is_refused_before_anything_runs(self) -> None:
        tck = _tck(_test("a"))
        with pytest.raises(UnknownFocusTestError, match="nope.yaml") as caught:
            resolve_only_ids(tck, {"only_tests": ["a.yaml", "nope.yaml"]})
        assert caught.value.test_ids == ["nope.yaml"]
        assert "focus" in str(caught.value)

    def test_a_host_refusing_bad_skips_refuses_it_too(self) -> None:
        assert issubclass(UnknownFocusTestError, SkipNotAllowedError)

    def test_skip_tests_is_still_validated(self) -> None:
        tck = _tck(_test("a"), _test("b"))
        with pytest.raises(SkipNotAllowedError, match="b.yaml"):
            resolve_plan(tck, {"only_tests": ["a.yaml"], "skip_tests": ["b.yaml"]})


class TestThePlan:
    def test_left_out_ids_join_skips_and_the_unselected(self) -> None:
        tests = [_test("a"), _test("b", skippable=True), _test("c")]
        plan = TestPlan(tests, skip_ids={"b.yaml"}, only_ids={"a.yaml", "b.yaml"})
        assert plan.left_out_ids == {"b.yaml", "c.yaml"}
        assert plan.only_tests == ["a.yaml", "b.yaml"]

    def test_a_plain_run_leaves_out_only_the_skips(self) -> None:
        plan = TestPlan([_test("a"), _test("b")], skip_ids={"b.yaml"})
        assert plan.left_out_ids == {"b.yaml"}
        assert plan.only_tests == []


@pytest.mark.asyncio
class TestFocusRun:
    async def test_only_the_selected_tests_run(self, outcomes) -> None:
        a, b, c = _test("a"), _test("b"), _test("c")
        session, jobs = _session(_tck(a, b, c), {"only_tests": ["b.yaml"]})

        await session.run_all()
        result = await session.close()

        assert outcomes.ran == ["b.yaml"]
        by_id = _by_id(result)
        assert by_id["a"].status == by_id["c"].status == TestStatus.SKIPPED
        assert by_id["a"].skip_reason == "not selected for this focus run"
        assert by_id["b"].skip_reason is None
        assert result.status == TestStatus.COMPLETED
        assert result.focus is True
        assert result.only_tests == ["b.yaml"]
        jobs.complete.assert_called_once()

    async def test_a_required_test_is_left_out_all_the_same(self, outcomes) -> None:
        """``skippable`` governs skip_tests, not a focus run."""
        a, b = _test("a", skippable=False), _test("b")
        session, _ = _session(_tck(a, b), {"only_tests": "b.yaml"})

        await session.run_all()
        result = await session.close()

        assert _by_id(result)["a"].skip_reason == NOT_SELECTED_REASON

    async def test_skip_tests_applies_on_top(self, outcomes) -> None:
        a, b, c = _test("a"), _test("b", skippable=True), _test("c")
        session, _ = _session(
            _tck(a, b, c), {"only_tests": ["a.yaml", "b.yaml"], "skip_tests": "b.yaml"}
        )

        await session.run_all()
        result = await session.close()

        assert outcomes.ran == ["a.yaml"]
        by_id = _by_id(result)
        assert by_id["b"].skip_reason is None  # skip_tests: as it always was
        assert by_id["c"].skip_reason == NOT_SELECTED_REASON

    async def test_a_plain_run_is_not_a_focus_run(self, outcomes) -> None:
        session, _ = _session(_tck(_test("a")))
        await session.run_all()
        result = await session.close()
        assert result.focus is False
        assert result.only_tests == []

    async def test_a_selected_stop_test_still_stops_the_rest_of_the_selection(
        self, outcomes
    ) -> None:
        a, b, c = _test("a", on_failure="stop"), _test("b"), _test("c")
        outcomes.planned["a.yaml"] = (TestStatus.FAILED, None)
        session, _ = _session(_tck(a, b, c), {"only_tests": ["a.yaml", "b.yaml"]})

        await session.run_all()
        result = await session.close()

        by_id = _by_id(result)
        assert by_id["b"].skip_reason == STOPPED_REASON.format(test_id="a.yaml")
        assert by_id["c"].skip_reason == NOT_SELECTED_REASON


# ---------------------------------------------------------------------------
# The trace
# ---------------------------------------------------------------------------


class TestTheTraceSaysWhy:
    def test_a_skip_with_a_reason_carries_it(self) -> None:
        skipped = make_intentionally_skipped_result(_test("a"), NOT_SELECTED_REASON)
        assert trace_test_data(skipped)["reason"] == NOT_SELECTED_REASON

    def test_an_operator_skip_is_written_as_it_always_was(self) -> None:
        skipped = make_intentionally_skipped_result(_test("a"))
        assert "reason" not in trace_test_data(skipped)

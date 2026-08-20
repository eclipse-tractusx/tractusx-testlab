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


"""What a finished run announces to the things watching it.

The CLI prints a verdict, the JSONL records one, and the IDE reads the JSONL.
All three must say the same thing about the same run — a green event stream
over a failed TCK is worse than no event stream, because it is believed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from tractusx_testlab.models import ScriptStatus, StepStatus
from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.runtime.results import (
    AssertionSummary,
    ScriptResult,
    StepResult,
    TckResult,
)
from tractusx_testlab.player.execution._trace_formatter import build_tck_result, finalize_job


def _step(status: StepStatus) -> StepResult:
    return StepResult(
        step_name=f"step-{status.value}",
        step_type="util/log",
        phase=StepPhase.EXECUTION,
        status=status,
    )


def _script(status: ScriptStatus, steps: list[StepResult]) -> ScriptResult:
    now = datetime.now(UTC)
    return ScriptResult(
        script_name="s",
        dataspace_version="saturn",
        status=status,
        execution=steps,
        started_at=now,
        finished_at=now,
        total_duration_s=0.0,
        assertion_summary=AssertionSummary(total=0, passed=0, failed_hard=0, failed_soft=0),
    )


class TestTheVerdictIsTheStatus:
    """`steps_passed` is a tally. The verdict is `status`, and only `status`."""

    def _mostly_passing(self) -> TckResult:
        now = datetime.now(UTC)
        steps = [_step(StepStatus.PASSED)] * 4 + [_step(StepStatus.FAILED)]
        return build_tck_result("tck", [_script(ScriptStatus.FAILED, steps)], now, now)

    def test_a_run_with_one_failed_step_is_failed(self) -> None:
        assert self._mostly_passing().status == ScriptStatus.FAILED

    def test_the_tally_counts_only_the_passing_steps(self) -> None:
        result = self._mostly_passing()
        assert (result.steps_passed, result.steps_total) == (4, 5)

    def test_the_event_stream_reports_the_failure(self) -> None:
        """The reproduction.

        ``finalize_job`` asked ``if result.passed:`` — a *count*, truthy for any
        run where a single step passed. A four-of-five run therefore published
        ``job_completed`` while the CLI printed FAIL from ``status``, and the
        IDE parsing those events showed a green job for a failed TCK.
        """
        jobs, monitor, logger = MagicMock(), MagicMock(), MagicMock()
        finalize_job(jobs, MagicMock(), self._mostly_passing(), monitor, logger)

        monitor.on_job_failed.assert_called_once()
        monitor.on_job_completed.assert_not_called()
        jobs.fail.assert_called_once()

    def test_a_wholly_passing_run_reports_completion(self) -> None:
        now = datetime.now(UTC)
        result = build_tck_result(
            "tck", [_script(ScriptStatus.COMPLETED, [_step(StepStatus.PASSED)])], now, now
        )
        jobs, monitor, logger = MagicMock(), MagicMock(), MagicMock()
        finalize_job(jobs, MagicMock(), result, monitor, logger)

        monitor.on_job_completed.assert_called_once()
        monitor.on_job_failed.assert_not_called()

    def test_a_run_where_every_step_failed_is_still_failed(self) -> None:
        """The one case the old code got right, kept so the fix is not a swap."""
        now = datetime.now(UTC)
        result = build_tck_result(
            "tck", [_script(ScriptStatus.FAILED, [_step(StepStatus.FAILED)])], now, now
        )
        assert result.status == ScriptStatus.FAILED
        assert result.steps_passed == 0

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Tests for flow/select and the wait it shares with every selection step."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import Job, StepDefinition, StepExecutionError
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.steps.flow.select import SelectStep


@pytest.fixture()
def jobs() -> JobManager:
    return JobManager()


@pytest.fixture()
def job(jobs: JobManager) -> Job:
    return jobs.create("tck")


@pytest.fixture()
def reporter() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def context(jobs: JobManager, job: Job, reporter: MagicMock) -> StepContext:
    ctx = StepContext(services=MagicMock(), job=job, config=MagicMock())
    ctx.hold.bind(jobs, job.job_id, MagicMock())
    ctx.bind_listener_reporter(reporter)
    return ctx


async def _select(context: StepContext, **params: object) -> dict:
    definition = StepDefinition(id="pick", uses="flow/select")
    output = await SelectStep().invoke(params, context, definition)
    return output.value


class TestWithoutAsking:
    @pytest.mark.asyncio
    async def test_a_single_option_is_taken_without_asking(
        self, context: StepContext, reporter: MagicMock
    ) -> None:
        value = await _select(context, options=["only"])
        assert (value["value"], value["selected_by"]) == ("only", "single")
        reporter.selecting.assert_not_called()

    @pytest.mark.asyncio
    async def test_values_have_to_be_unique(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="unique: a"):
            await _select(context, options=["a", "a"])


class TestAskingTheOperator:
    @pytest.mark.asyncio
    async def test_the_operator_chooses_from_a_dropdown(
        self, context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
    ) -> None:
        reporter.selecting.side_effect = lambda *_: jobs.selections.answer(job.job_id, "b", "pick")
        value = await _select(
            context, options=["a", {"value": "b", "label": "Bee", "details": {"n": 2}}]
        )

        assert value == {
            "value": "b",
            "label": "Bee",
            "details": {"n": 2},
            "selected_by": "operator",
        }
        selection = reporter.selecting.call_args.args[2]
        assert selection.presentation == "dropdown"
        assert [(option.id, option.label) for option in selection.options] == [
            ("a", "a"),
            ("b", "Bee"),
        ]
        assert reporter.selected.call_args.args[2].id == "b"
        assert jobs.selections.pending(job.job_id) is None

    @pytest.mark.asyncio
    async def test_auto_select_single_off_asks_for_one_option_too(
        self, context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
    ) -> None:
        reporter.selecting.side_effect = lambda *_: jobs.selections.answer(job.job_id, "only")
        value = await _select(context, options=["only"], auto_select_single=False)
        assert value["selected_by"] == "operator"

    @pytest.mark.asyncio
    async def test_no_answer_within_the_timeout_fails(
        self, context: StepContext, jobs: JobManager, job: Job
    ) -> None:
        with pytest.raises(StepExecutionError, match="nothing was chosen within"):
            await _select(context, options=["a", "b"], timeout_s=0.05)
        assert jobs.selections.pending(job.job_id) is None

    @pytest.mark.asyncio
    async def test_cancelling_the_run_withdraws_the_question(
        self, context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
    ) -> None:
        reporter.selecting.side_effect = lambda *_: jobs.cancel(job.job_id)
        with pytest.raises(StepExecutionError, match="cancelled before anything was chosen"):
            await _select(context, options=["a", "b"])

    @pytest.mark.asyncio
    async def test_a_pause_stops_the_clock_and_asks_again_on_resume(
        self, context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
    ) -> None:
        jobs.start(job.job_id)
        loop = asyncio.get_running_loop()

        def asked(*args: object) -> None:
            if reporter.selecting.call_count == 1:
                jobs.pause(job.job_id)
                loop.call_later(0.05, jobs.resume, job.job_id)
            else:
                jobs.selections.answer(job.job_id, "a")

        reporter.selecting.side_effect = asked
        value = await _select(context, options=["a", "b"], timeout_s=1)

        assert value["value"] == "a"
        assert reporter.selecting.call_count == 2
        assert reporter.selecting.call_args.args[3] <= 1

    @pytest.mark.asyncio
    async def test_without_a_player_nobody_can_be_asked(self, job: Job) -> None:
        ctx = StepContext(services=MagicMock(), job=job, config=MagicMock())
        with pytest.raises(StepExecutionError, match="no operator to choose"):
            await _select(ctx, options=["a", "b"])


class TestSelectionBoard:
    @pytest.mark.asyncio
    async def test_an_answer_has_to_be_an_option(self, jobs: JobManager) -> None:
        jobs.selections.ask("job-1", "pick", ["a", "b"])
        with pytest.raises(ValueError, match="'c' is not one of the options offered"):
            jobs.selections.answer("job-1", "c")

    @pytest.mark.asyncio
    async def test_an_answer_for_another_step_is_refused(self, jobs: JobManager) -> None:
        jobs.selections.ask("job-1", "pick", ["a"])
        with pytest.raises(LookupError, match="at step 'pick', not 'other'"):
            jobs.selections.answer("job-1", "a", "other")

    def test_a_job_that_asks_nothing_cannot_be_answered(self, jobs: JobManager) -> None:
        with pytest.raises(LookupError, match="not waiting for a selection"):
            jobs.selections.answer("job-1", "a")

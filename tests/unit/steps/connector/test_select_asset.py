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

"""Tests for connector/query_catalog/select_asset."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import Job, StepDefinition, StepExecutionError
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.steps.connector.select_asset import SelectAssetStep

_PARTY = {
    "counter_party_id": "BPNL_PROVIDER",
    "counter_party_address": "https://provider.example/dsp",
}
_OFFER = {"@id": "offer-1", "odrl:permission": {"odrl:action": {"@id": "odrl:use"}}}
_DATASETS = [
    {"@id": "ccmapi-1", "dct:type": {"@id": "cx-taxo:CCMAPI"}, "odrl:hasPolicy": _OFFER},
    {"@id": "ccmapi-2", "dct:type": {"@id": "cx-taxo:CCMAPI"}, "odrl:hasPolicy": [_OFFER, _OFFER]},
]


@pytest.fixture()
def consumer() -> MagicMock:
    svc = MagicMock()
    svc.get_catalog_with_filter.return_value = {"dcat:dataset": list(_DATASETS)}
    svc.dataspace_version = "jupiter"
    return svc


@pytest.fixture()
def jobs() -> JobManager:
    return JobManager()


@pytest.fixture()
def job(jobs: JobManager) -> Job:
    return jobs.create("ccm-tck")


@pytest.fixture()
def reporter() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def context(consumer: MagicMock, jobs: JobManager, job: Job, reporter: MagicMock) -> StepContext:
    ctx = StepContext(services=MagicMock(), job=job, config=MagicMock())
    ctx.services.service_names = ["connector"]
    ctx.services.get.return_value = consumer
    ctx.hold.bind(jobs, job.job_id, MagicMock())
    ctx.bind_listener_reporter(reporter)
    return ctx


def _definition() -> StepDefinition:
    return StepDefinition(id="select", uses="connector/query_catalog/select_asset")


async def _select(context: StepContext, **params: object) -> dict:
    output = await SelectAssetStep().invoke({**_PARTY, **params}, context, _definition())
    return output.value


class TestWithoutAsking:
    @pytest.mark.asyncio
    async def test_a_single_asset_is_taken_without_asking(
        self, context: StepContext, consumer: MagicMock, reporter: MagicMock
    ) -> None:
        consumer.get_catalog_with_filter.return_value = {"dcat:dataset": _DATASETS[0]}
        value = await _select(context)
        assert (value["asset_id"], value["selected_by"]) == ("ccmapi-1", "single")
        reporter.selecting.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_asset_named_up_front_is_taken(
        self, context: StepContext, reporter: MagicMock
    ) -> None:
        value = await _select(context, asset_id="ccmapi-2")
        assert (value["asset_id"], value["selected_by"]) == ("ccmapi-2", "input")
        assert value["dataset"] == _DATASETS[1]
        reporter.selecting.assert_not_called()

    @pytest.mark.asyncio
    async def test_an_asset_named_up_front_has_to_be_in_the_catalog(
        self, context: StepContext
    ) -> None:
        with pytest.raises(StepExecutionError, match="'ccmapi-9' is not in the catalog"):
            await _select(context, asset_id="ccmapi-9")

    @pytest.mark.asyncio
    async def test_an_empty_catalog_fails(self, context: StepContext, consumer: MagicMock) -> None:
        consumer.get_catalog_with_filter.return_value = {"dcat:dataset": []}
        with pytest.raises(StepExecutionError, match="offers no asset"):
            await _select(context)


class TestAskingTheOperator:
    @pytest.mark.asyncio
    async def test_the_operator_chooses_among_the_options(
        self, context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
    ) -> None:
        reporter.selecting.side_effect = lambda *_: jobs.selections.answer(
            job.job_id, "ccmapi-2", "select"
        )
        value = await _select(context)

        assert (value["asset_id"], value["selected_by"]) == ("ccmapi-2", "operator")
        assert value["dataset"] == _DATASETS[1]
        selection = reporter.selecting.call_args.args[2]
        assert [option.asset_id for option in selection.options] == ["ccmapi-1", "ccmapi-2"]
        assert selection.options[0].properties == {"dct:type": {"@id": "cx-taxo:CCMAPI"}}
        assert selection.options[0].policies == [_OFFER]
        assert len(selection.options[1].policies) == 2
        assert reporter.selected.call_args.args[2] == "ccmapi-2"
        assert jobs.selections.pending(job.job_id) is None

    @pytest.mark.asyncio
    async def test_ask_if_single_asks_for_one_asset_too(
        self,
        context: StepContext,
        consumer: MagicMock,
        jobs: JobManager,
        job: Job,
        reporter: MagicMock,
    ) -> None:
        consumer.get_catalog_with_filter.return_value = {"dcat:dataset": _DATASETS[0]}
        reporter.selecting.side_effect = lambda *_: jobs.selections.answer(job.job_id, "ccmapi-1")
        value = await _select(context, ask_if_single=True)
        assert value["selected_by"] == "operator"

    @pytest.mark.asyncio
    async def test_no_answer_within_the_timeout_fails(
        self, context: StepContext, jobs: JobManager, job: Job
    ) -> None:
        with pytest.raises(StepExecutionError, match="no asset was chosen within"):
            await _select(context, timeout_s=0.05)
        assert jobs.selections.pending(job.job_id) is None

    @pytest.mark.asyncio
    async def test_cancelling_the_run_withdraws_the_question(
        self, context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
    ) -> None:
        reporter.selecting.side_effect = lambda *_: jobs.cancel(job.job_id)
        with pytest.raises(StepExecutionError, match="cancelled before an asset was chosen"):
            await _select(context)

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
                jobs.selections.answer(job.job_id, "ccmapi-1")

        reporter.selecting.side_effect = asked
        value = await _select(context, timeout_s=1)

        assert value["asset_id"] == "ccmapi-1"
        assert reporter.selecting.call_count == 2
        assert reporter.selecting.call_args.args[3] <= 1

    @pytest.mark.asyncio
    async def test_without_a_player_nobody_can_be_asked(
        self, consumer: MagicMock, job: Job
    ) -> None:
        ctx = StepContext(services=MagicMock(), job=job, config=MagicMock())
        ctx.services.service_names = ["connector"]
        ctx.services.get.return_value = consumer
        with pytest.raises(StepExecutionError, match="no operator to choose an asset"):
            await _select(ctx)


class TestSelectionBoard:
    @pytest.mark.asyncio
    async def test_an_answer_has_to_be_an_option(self, jobs: JobManager) -> None:
        jobs.selections.ask("job-1", "select", ["a", "b"])
        with pytest.raises(ValueError, match="'c' is not one of the assets offered"):
            jobs.selections.answer("job-1", "c")

    @pytest.mark.asyncio
    async def test_an_answer_for_another_step_is_refused(self, jobs: JobManager) -> None:
        jobs.selections.ask("job-1", "select", ["a"])
        with pytest.raises(LookupError, match="at step 'select', not 'other'"):
            jobs.selections.answer("job-1", "a", "other")

    def test_a_job_that_asks_nothing_cannot_be_answered(self, jobs: JobManager) -> None:
        with pytest.raises(LookupError, match="not waiting for an asset"):
            jobs.selections.answer("job-1", "a")

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

"""Tests for connector/datasets/select."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import Job, StepDefinition, StepExecutionError
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.steps.connector.datasets_select import SelectDatasetStep

_USE = {"@id": "offer-use", "odrl:permission": {"odrl:action": {"@id": "odrl:use"}}}
_READ = {"@id": "offer-read", "odrl:permission": {"odrl:action": {"@id": "odrl:read"}}}
_DATASETS = [
    {"@id": "ccmapi-1", "dct:type": {"@id": "cx-taxo:CCMAPI"}, "odrl:hasPolicy": _USE},
    {
        "@id": "ccmapi-2",
        "dct:type": {"@id": "cx-taxo:CCMAPI"},
        "odrl:hasPolicy": [_USE, _READ],
        "dcat:distribution": [{"dct:format": {"@id": "HttpData-PULL"}}],
    },
    {"@id": "no-offer", "dct:type": {"@id": "cx-taxo:CCMAPI"}},
]


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
def context(jobs: JobManager, job: Job, reporter: MagicMock) -> StepContext:
    ctx = StepContext(services=MagicMock(), job=job, config=MagicMock())
    ctx.hold.bind(jobs, job.job_id, MagicMock())
    ctx.bind_listener_reporter(reporter)
    return ctx


async def _select(context: StepContext, **params: object) -> dict:
    definition = StepDefinition(id="offer", uses="connector/datasets/select")
    output = await SelectDatasetStep().invoke(params, context, definition)
    return output.value


@pytest.mark.asyncio
async def test_every_asset_offer_pair_is_an_option(
    context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
) -> None:
    reporter.selecting.side_effect = lambda *_: jobs.selections.answer(
        job.job_id, "ccmapi-2::offer-read", "offer"
    )
    value = await _select(context, datasets=_DATASETS)

    selection = reporter.selecting.call_args.args[2]
    assert selection.presentation == "catalog_offers"
    assert [option.id for option in selection.options] == [
        "ccmapi-1::offer-use",
        "ccmapi-2::offer-use",
        "ccmapi-2::offer-read",
    ]
    details = selection.options[2].details
    assert details["properties"] == {"dct:type": {"@id": "cx-taxo:CCMAPI"}}
    assert (details["offer_index"], details["offer_count"], details["policy"]) == (2, 2, _READ)

    assert value["asset_id"] == "ccmapi-2"
    assert value["offer_id"] == "offer-read"
    assert value["policy"] == _READ
    assert value["dataset"] == _DATASETS[1]
    assert value["selected_by"] == "operator"


@pytest.mark.asyncio
async def test_the_only_pair_is_taken_without_asking(
    context: StepContext, reporter: MagicMock
) -> None:
    value = await _select(context, datasets=_DATASETS[0])
    assert (value["asset_id"], value["policy"], value["selected_by"]) == (
        "ccmapi-1",
        _USE,
        "single",
    )
    reporter.selecting.assert_not_called()


@pytest.mark.asyncio
async def test_auto_select_single_off_asks_for_the_only_pair(
    context: StepContext, jobs: JobManager, job: Job, reporter: MagicMock
) -> None:
    reporter.selecting.side_effect = lambda *_: jobs.selections.answer(
        job.job_id, "ccmapi-1::offer-use"
    )
    value = await _select(context, datasets=[_DATASETS[0]], auto_select_single=False)
    assert value["selected_by"] == "operator"


@pytest.mark.asyncio
async def test_datasets_without_offers_leave_nothing_to_choose(context: StepContext) -> None:
    with pytest.raises(StepExecutionError, match="nothing to choose from"):
        await _select(context, datasets=[_DATASETS[2]])


@pytest.mark.asyncio
async def test_repeated_offers_keep_their_options_apart(
    context: StepContext, reporter: MagicMock, jobs: JobManager, job: Job
) -> None:
    twice = {"@id": "a", "odrl:hasPolicy": [_USE, _USE]}
    reporter.selecting.side_effect = lambda *_: jobs.selections.answer(job.job_id, "a::offer-use#2")
    value = await _select(context, datasets=[twice])
    ids = [option.id for option in reporter.selecting.call_args.args[2].options]
    assert ids == ["a::offer-use", "a::offer-use#2"]
    assert value["asset_id"] == "a"

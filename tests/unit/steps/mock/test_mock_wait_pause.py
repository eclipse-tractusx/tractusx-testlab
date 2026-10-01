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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""``mock/wait`` across a pause: the clock stops, and carries on with what was left."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.hold import RunHold
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.inbound.run_scope import scoped
from tractusx_testlab.server.mock_registry import clear_mocks, set_callback_manager
from tractusx_testlab.steps.mock.api import MockEndpointStep
from tractusx_testlab.steps.mock.wait import WaitForCallStep

_PATH = "/companycertificate/push"


def _definition(uses: str) -> StepDefinition:
    return StepDefinition(id="s", uses=uses)


def _key(context: MagicMock) -> str:
    """Where the run's listener on ``_PATH`` is kept, and so where its call lands."""
    return scoped(str(context.job.job_id), _PATH)


@pytest.fixture()
def jobs() -> JobManager:
    return JobManager()


@pytest.fixture()
def context(mock_context: MagicMock, jobs: JobManager) -> MagicMock:
    job = jobs.create("tck")
    jobs.start(job.job_id)
    mock_context.job.job_id = job.job_id
    mock_context.config.mock_public_url = "http://engine.example/mock/run"
    hold = RunHold()
    hold.bind(jobs, job.job_id, MagicMock())
    mock_context.hold = hold
    clear_mocks()
    yield mock_context
    clear_mocks()


async def _register(context: MagicMock) -> dict[str, Any]:
    registered = await MockEndpointStep().invoke(
        {"path": _PATH, "method": "POST"}, context, _definition("mock/api")
    )
    return registered.value["mock"]


def _waiting_timeouts(context: MagicMock) -> list[float]:
    return [c.args[3] for c in context.report_waiting.call_args_list]


class TestAPauseDuringTheWait:
    @pytest.mark.asyncio
    async def test_the_wait_stops_and_says_what_is_left(
        self, context: MagicMock, jobs: JobManager
    ) -> None:
        manager = CallbackManager()
        set_callback_manager(manager)
        mock = await _register(context)
        wait = asyncio.ensure_future(
            WaitForCallStep().invoke(
                {"mock": mock, "timeout_s": 5}, context, _definition("mock/wait/http_request")
            )
        )
        await asyncio.sleep(0.1)
        jobs.pause(context.job.job_id)
        await asyncio.sleep(0.05)

        context.report_suspended.assert_called_once()
        remaining = context.report_suspended.call_args.args[3]
        assert 4.5 < remaining < 5
        assert jobs.is_held(context.job.job_id)
        assert not manager.has_listener(_key(context), "POST")  # nothing listens while held

        jobs.resume(context.job.job_id)
        await asyncio.sleep(0.05)
        assert _waiting_timeouts(context) == [5, remaining]

        manager.resolve(_key(context), "POST", {}, {"status": "RECEIVED"})
        output = await asyncio.wait_for(wait, 1)
        assert output.value["request_body"] == {"status": "RECEIVED"}

    @pytest.mark.asyncio
    async def test_the_time_on_hold_is_not_counted(
        self, context: MagicMock, jobs: JobManager
    ) -> None:
        manager = CallbackManager()
        set_callback_manager(manager)
        mock = await _register(context)
        wait = asyncio.ensure_future(
            WaitForCallStep().invoke(
                {"mock": mock, "timeout_s": 5}, context, _definition("mock/wait/http_request")
            )
        )
        await asyncio.sleep(0.05)
        jobs.pause(context.job.job_id)
        await asyncio.sleep(0.4)
        jobs.resume(context.job.job_id)
        await asyncio.sleep(0.05)
        manager.resolve(_key(context), "POST", {}, None)

        output = await asyncio.wait_for(wait, 1)
        assert output.value["elapsed_ms"] < 350

    @pytest.mark.asyncio
    async def test_after_the_resume_it_times_out_on_what_was_left(
        self, context: MagicMock, jobs: JobManager
    ) -> None:
        set_callback_manager(CallbackManager())
        mock = await _register(context)
        wait = asyncio.ensure_future(
            WaitForCallStep().invoke(
                {"mock": mock, "timeout_s": 0.3}, context, _definition("mock/wait/http_request")
            )
        )
        await asyncio.sleep(0.1)
        jobs.pause(context.job.job_id)
        await asyncio.sleep(0.5)  # longer than the whole timeout
        assert not wait.done()

        jobs.resume(context.job.job_id)
        with pytest.raises(RuntimeError, match="Timed out"):
            await asyncio.wait_for(wait, 1)

    @pytest.mark.asyncio
    async def test_a_call_that_came_before_the_pause_is_not_lost(
        self, context: MagicMock, jobs: JobManager
    ) -> None:
        manager = CallbackManager()
        set_callback_manager(manager)
        mock = await _register(context)
        manager.resolve(_key(context), "POST", {}, {"early": True})
        jobs.pause(context.job.job_id)

        output = await asyncio.wait_for(
            WaitForCallStep().invoke(
                {"mock": mock, "timeout_s": 5}, context, _definition("mock/wait/http_request")
            ),
            1,
        )

        assert output.value["request_body"] == {"early": True}
        context.report_suspended.assert_not_called()

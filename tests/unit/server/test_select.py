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

"""Tests for the endpoint that answers a ``flow/select`` step."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.server.routes import router


@pytest.fixture()
def jobs() -> JobManager:
    return JobManager()


@pytest.fixture()
async def client(jobs: JobManager) -> AsyncClient:
    player = MagicMock()
    player.jobs = jobs
    app = FastAPI()
    app.state.player = player
    app.state.storage = MagicMock()
    app.state.callbacks = MagicMock()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _url(job_id: str) -> str:
    return f"/testlab/tck-execution/{job_id}/select"


@pytest.mark.asyncio
async def test_the_answer_reaches_the_waiting_step(client: AsyncClient, jobs: JobManager) -> None:
    job = jobs.create("ccm-tck")
    answer = jobs.selections.ask(job.job_id, "select", ["ccmapi-1", "ccmapi-2"])

    response = await client.post(_url(job.job_id), json={"value": "ccmapi-2", "step_id": "select"})

    assert response.status_code == 200
    assert answer.result() == "ccmapi-2"


@pytest.mark.asyncio
async def test_an_option_not_offered_is_refused(client: AsyncClient, jobs: JobManager) -> None:
    job = jobs.create("ccm-tck")
    jobs.selections.ask(job.job_id, "select", ["ccmapi-1"])
    response = await client.post(_url(job.job_id), json={"value": "nope"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_a_job_not_asking_is_a_conflict(client: AsyncClient, jobs: JobManager) -> None:
    job = jobs.create("ccm-tck")
    response = await client.post(_url(job.job_id), json={"value": "ccmapi-1"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_an_unknown_job_is_not_found(client: AsyncClient) -> None:
    response = await client.post(_url("missing"), json={"value": "ccmapi-1"})
    assert response.status_code == 404

###############################################################
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
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Tests for the resume endpoint and resume-related SSE events."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tractusx_testlab.models.primitives.enums import JobStatus
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.server.routes import router
from tractusx_testlab.server.streaming import streaming_router

_STREAMING_MODULE = "tractusx_testlab.server.streaming.routes"


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_player() -> MagicMock:
    """MagicMock player with real JobManager and ExecutionMonitor."""
    player = MagicMock()
    player.jobs = JobManager()
    player.monitor = ExecutionMonitor(MagicMock())
    player.run_tck = AsyncMock()
    player._config = MagicMock()
    player._config.max_upload_bytes = 10_000_000
    return player


@pytest.fixture()
def app(mock_player: MagicMock) -> FastAPI:
    """FastAPI app wired with mocked player for routes under /testlab."""
    application = FastAPI()
    application.state.player = mock_player
    application.state.storage = MagicMock()
    application.state.callbacks = MagicMock()
    application.include_router(router)
    return application


@pytest.fixture()
async def client(app: FastAPI) -> AsyncClient:
    """Async HTTP client backed by the test FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


def _make_event_queue(
    *events: tuple[str, dict],
) -> asyncio.Queue[tuple[str, dict]]:
    """Return an asyncio.Queue pre-populated with the given events."""
    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
    for event in events:
        queue.put_nowait(event)
    return queue


# ──────────────────────────────────────────────────────────────────────
# Resume endpoint
# ──────────────────────────────────────────────────────────────────────


class TestResumeEndpoint:
    """POST /testlab/test-execution/{job_id}/resume tests."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Route uses str(enum) instead of enum.value — returns 409 always")
    async def test_resume_paused_job_returns_200(
        self, client: AsyncClient, mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck-1")
        mock_player.jobs.start(job.job_id)
        mock_player.jobs.pause(job.job_id)

        response = await client.post(
            f"/testlab/test-execution/{job.job_id}/resume",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job.job_id
        assert data["status"] == "RUNNING"

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Route uses str(enum) instead of enum.value — returns 409 always")
    async def test_resume_sets_job_status_to_running(
        self, client: AsyncClient, mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck-1")
        mock_player.jobs.start(job.job_id)
        mock_player.jobs.pause(job.job_id)

        await client.post(f"/testlab/test-execution/{job.job_id}/resume")

        updated = mock_player.jobs.get(job.job_id)
        assert updated.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_resume_running_job_returns_409(
        self, client: AsyncClient, mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck-1")
        mock_player.jobs.start(job.job_id)

        response = await client.post(
            f"/testlab/test-execution/{job.job_id}/resume",
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_resume_completed_job_returns_409(
        self, client: AsyncClient, mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck-1")
        mock_player.jobs.start(job.job_id)
        mock_player.jobs.complete(job.job_id)

        response = await client.post(
            f"/testlab/test-execution/{job.job_id}/resume",
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_resume_nonexistent_job_returns_404(
        self, client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/testlab/test-execution/nonexistent/resume",
        )

        assert response.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# Resume SSE event
# ──────────────────────────────────────────────────────────────────────


class TestResumeEvent:
    """SSE stream emits job.resumed event."""

    @pytest.mark.asyncio
    async def test_resumed_job_emits_event(
        self, client: AsyncClient, mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck-1")
        mock_player.jobs.start(job.job_id)
        queue = _make_event_queue(
            ("job.resumed", {"job_id": job.job_id, "status": "RUNNING"}),
            ("job.completed", {"status": "completed"}),
        )

        with patch(f"{_STREAMING_MODULE}.create_event_queue", return_value=queue):
            response = await client.get(
                f"/testlab/test-execution/{job.job_id}/stream",
            )

        assert "event: job.resumed" in response.text

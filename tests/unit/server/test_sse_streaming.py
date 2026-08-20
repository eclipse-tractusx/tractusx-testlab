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

"""Tests for SSE streaming endpoints and CORS middleware."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.jobs import JobManager
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
    return player


@pytest.fixture()
def app(mock_player: MagicMock) -> FastAPI:
    """FastAPI app wired with mocked player and CORS middleware."""
    application = FastAPI()
    application.state.player = mock_player
    application.state.storage = MagicMock()
    application.state.callbacks = MagicMock()
    application.include_router(streaming_router, prefix="/testlab")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
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
# YAML Submission
# ──────────────────────────────────────────────────────────────────────


class TestYamlSubmission:
    """POST /testlab/test-execution/run endpoint tests."""

    @pytest.mark.asyncio
    async def test_run_yaml_returns_job_id(
        self,
        client: AsyncClient,
        mock_player: MagicMock,
    ) -> None:
        mock_def = MagicMock()
        mock_def.name = "my-test"
        mock_tc = MagicMock()
        mock_tc.name = "my-test"

        with (
            patch(f"{_STREAMING_MODULE}.YamlParser") as parser_cls,
            patch(f"{_STREAMING_MODULE}.Tck") as tck_cls,
        ):
            parser_cls.return_value.parse_script_from_dict.return_value = mock_def
            tck_cls.from_single_script.return_value = mock_tc
            tck_cls.return_value = mock_tc
            response = await client.post(
                "/testlab/test-execution/run",
                content=b"name: my-test\nsteps: []",
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_run_yaml_rejects_invalid_yaml(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/testlab/test-execution/run",
            content=b"{{invalid: yaml: : :",
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_run_yaml_rejects_empty_body(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post("/testlab/test-execution/run", content=b"")
        assert response.status_code == 400


# ──────────────────────────────────────────────────────────────────────
# SSE Streaming
# ──────────────────────────────────────────────────────────────────────


class TestSseStreaming:
    """GET /testlab/test-execution/{job_id}/stream endpoint tests."""

    @pytest.mark.asyncio
    async def test_stream_returns_event_stream_content_type(
        self,
        client: AsyncClient,
        mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck")
        queue = _make_event_queue(("job.completed", {"status": "completed"}))

        with patch(f"{_STREAMING_MODULE}.create_event_queue", return_value=queue):
            response = await client.get(f"/testlab/test-execution/{job.job_id}/stream")

        assert "text/event-stream" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_stream_unknown_job_returns_404(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get("/testlab/test-execution/nonexistent/stream")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_emits_step_events(
        self,
        client: AsyncClient,
        mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck")
        queue = _make_event_queue(
            ("step.started", {"step_index": 0, "step_type": "connector/provider/create_asset"}),
            (
                "step.completed",
                {"step_name": "connector/provider/create_asset", "status": "passed"},
            ),
            ("job.completed", {"status": "completed"}),
        )

        with patch(f"{_STREAMING_MODULE}.create_event_queue", return_value=queue):
            response = await client.get(f"/testlab/test-execution/{job.job_id}/stream")

        body = response.text
        assert "event: step.started" in body
        assert "event: step.completed" in body

    @pytest.mark.asyncio
    async def test_stream_emits_job_completed(
        self,
        client: AsyncClient,
        mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck")
        queue = _make_event_queue(
            ("job.completed", {"job_id": job.job_id, "status": "completed"}),
        )

        with patch(f"{_STREAMING_MODULE}.create_event_queue", return_value=queue):
            response = await client.get(f"/testlab/test-execution/{job.job_id}/stream")

        body = response.text
        assert "event: job.completed" in body
        assert job.job_id in body

    @pytest.mark.asyncio
    async def test_stream_event_format_is_valid_sse(
        self,
        client: AsyncClient,
        mock_player: MagicMock,
    ) -> None:
        job = mock_player.jobs.create("tck")
        queue = _make_event_queue(
            ("step.started", {"step_index": 0}),
            ("job.completed", {"status": "completed"}),
        )

        with patch(f"{_STREAMING_MODULE}.create_event_queue", return_value=queue):
            response = await client.get(f"/testlab/test-execution/{job.job_id}/stream")

        messages = response.text.strip().split("\n\n")
        for msg in messages:
            lines = msg.strip().split("\n")
            assert len(lines) >= 3, f"SSE message needs id + event + data lines: {msg}"
            assert lines[0].startswith("id: "), f"Missing id field: {lines[0]}"
            assert lines[1].startswith("event: "), f"Missing event field: {lines[1]}"
            assert lines[2].startswith("data: "), f"Missing data field: {lines[2]}"
            data_str = lines[2].removeprefix("data: ")
            json.loads(data_str)  # must be valid JSON


# ──────────────────────────────────────────────────────────────────────
# CORS Middleware
# ──────────────────────────────────────────────────────────────────────


class TestCorsMiddleware:
    """CORS middleware behavior on the Testlab app."""

    @pytest.mark.asyncio
    async def test_cors_headers_present_on_response(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get(
            "/testlab/test-execution/nonexistent/stream",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.headers.get("access-control-allow-origin") == "*"

    @pytest.mark.asyncio
    async def test_cors_preflight_options(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.options(
            "/testlab/run",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"
        assert "POST" in response.headers.get("access-control-allow-methods", "")

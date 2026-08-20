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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""SSE streaming routes for live test execution events."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from tractusx_testlab.models.primitives.enums import ScriptKind
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.scripting.parser import YamlParser
from tractusx_testlab.scripting.script import Tck
from tractusx_testlab.server.streaming._event_buffer import EventBuffer
from tractusx_testlab.server.streaming.lifecycle import create_event_queue, sse_event_generator

_logger = logging.getLogger(__name__)

# Pending jobs: job_id → Tck (execution deferred until SSE stream connects)
_pending_jobs: dict[str, Tck] = {}

# Background task references — prevents garbage collection and logs exceptions
_background_tasks: set[asyncio.Task] = set()


def _on_task_done(task: asyncio.Task) -> None:
    """Remove completed task from the tracking set and log any unhandled exceptions."""
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _logger.exception("Background task failed: %s", exc, exc_info=exc)


streaming_router = APIRouter(prefix="/test-execution", tags=["streaming"])


def _get_player(request: Request) -> TestlabPlayer:
    return request.app.state.player


def _get_event_buffer(request: Request) -> EventBuffer:
    """Lazy-init the event buffer on app state."""
    if not hasattr(request.app.state, "event_buffer"):
        request.app.state.event_buffer = EventBuffer()
    return request.app.state.event_buffer


# Annotated dependency aliases
PlayerDep = Annotated[TestlabPlayer, Depends(_get_player)]
EventBufferDep = Annotated[EventBuffer, Depends(_get_event_buffer)]


# ──────────────────────────────────────────────────────────────────────
# YAML execution endpoint
# ──────────────────────────────────────────────────────────────────────


async def _parse_and_execute_yaml(request: Request, player: TestlabPlayer) -> JSONResponse:
    """Parse a YAML body, create a job, and launch background execution."""
    raw = await request.body()
    if not raw:
        raise HTTPException(400, "Request body must contain YAML content")

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise HTTPException(400, f"Invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise HTTPException(400, "YAML root must be a mapping")

    parser = YamlParser()
    kind_value = data.get("kind")
    has_tests = "tests" in data
    if kind_value:
        kind = ScriptKind(kind_value)
    elif has_tests:
        kind = ScriptKind.TCK
    else:
        kind = ScriptKind.TEST

    try:
        if kind == ScriptKind.TCK:
            tck_def = parser.parse_tck_from_dict(data)
            tck = Tck(tck_def)
        else:
            script_def = parser.parse_script_from_dict(data)
            tck = Tck.from_single_script(script_def)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"Failed to parse YAML definition: {exc}") from exc

    job = player.jobs.create(tck.name)
    _pending_jobs[job.job_id] = tck

    return JSONResponse(
        content={"job_id": job.job_id, "status": "queued"},
        status_code=202,
    )


@streaming_router.post(
    "/run",
    status_code=202,
    responses={
        400: {"description": "Request body is empty or contains invalid YAML"},
        422: {"description": "YAML definition could not be parsed"},
    },
)
async def run_test_yaml(
    request: Request,
    player: PlayerDep,
) -> JSONResponse:
    """Execute a TCK from a raw YAML body.

    Primary endpoint used by the IDE frontend.
    Accepts ``Content-Type: application/x-yaml`` or ``text/yaml``.
    Returns ``{"job_id": "...", "status": "queued"}``.
    """
    return await _parse_and_execute_yaml(request, player)


@streaming_router.post(
    "/run/yaml",
    status_code=202,
    responses={
        400: {"description": "Request body is empty or contains invalid YAML"},
        422: {"description": "YAML definition could not be parsed"},
    },
)
async def run_yaml(
    request: Request,
    player: PlayerDep,
) -> JSONResponse:
    """Execute a TCK from a raw YAML body (legacy alias for /run).

    Accepts ``Content-Type: application/x-yaml`` or ``text/yaml``.
    Returns ``{"job_id": "...", "status": "queued"}``.
    """
    return await _parse_and_execute_yaml(request, player)


async def _execute_tck_bg(
    player: TestlabPlayer,
    tck: Tck,
    job_id: str,
) -> None:
    """Run a TCK in the background, emitting failure events on exception."""
    try:
        await player.run_tck(tck, job_id=job_id)
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as exc:
        _logger.warning("Background execution failed for job %s: %s", job_id, type(exc).__name__)
        player.monitor._emit(
            "job.completed",
            job_id=job_id,
            status="FAILED",
            error=str(exc),
        )
        player.jobs.fail(job_id, str(exc))


# ──────────────────────────────────────────────────────────────────────
# SSE streaming endpoint
# ──────────────────────────────────────────────────────────────────────


@streaming_router.get(
    "/{job_id}/stream",
    responses={
        404: {"description": "Job not found"},
    },
)
async def stream_job_events(
    job_id: str,
    request: Request,
    player: PlayerDep,
    event_buffer: EventBufferDep,
) -> StreamingResponse:
    """Stream live execution events for a job via Server-Sent Events.

    Supports reconnection: send ``Last-Event-ID`` header to replay missed events.
    """
    job = player.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")

    last_event_id_raw = request.headers.get("last-event-id")
    last_event_id: int | None = None
    if last_event_id_raw is not None:
        try:
            last_event_id = int(last_event_id_raw)
        except ValueError:
            last_event_id = None

    queue = create_event_queue(player.monitor)

    # Start execution NOW — after the queue is registered so no events are lost
    tck = _pending_jobs.pop(job_id, None)
    if tck is not None:
        task = asyncio.create_task(_execute_tck_bg(player, tck, job_id))
        _background_tasks.add(task)
        task.add_done_callback(_on_task_done)

    return StreamingResponse(
        sse_event_generator(queue, job_id, event_buffer, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

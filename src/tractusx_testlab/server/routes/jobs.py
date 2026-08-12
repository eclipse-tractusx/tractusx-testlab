#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""FastAPI routes for job execution and management."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from tractusx_testlab.models import JobStatus
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.server.storage import PackageStorage

from tractusx_testlab.server.routes.callbacks import callback_router
from tractusx_testlab.server.routes.compile import compile_router
from tractusx_testlab.server.streaming import streaming_router

_logger = logging.getLogger(__name__)

# Background task references — prevents garbage collection and logs exceptions
_background_tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]


def _on_task_done(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Remove completed task from the tracking set and log any unhandled exceptions."""
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _logger.exception("Background task failed: %s", exc, exc_info=exc)


router = APIRouter(prefix="/testlab", tags=["testlab"])
router.include_router(streaming_router)
router.include_router(compile_router)
router.include_router(callback_router)

# Background task references — prevents garbage collection and logs exceptions
_background_tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]


def _on_task_done(task: asyncio.Task) -> None:  # type: ignore[type-arg]
    """Remove completed task from the tracking set and log any unhandled exceptions."""
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _logger.exception("Background execution task failed: %s", exc, exc_info=exc)


def _get_player(request: Request) -> TestlabPlayer:
    return request.app.state.player


def _get_storage(request: Request) -> PackageStorage:
    return request.app.state.storage


# Annotated dependency aliases
PlayerDep = Annotated[TestlabPlayer, Depends(_get_player)]
StorageDep = Annotated[PackageStorage, Depends(_get_storage)]


# ──────────────────────────────────────────────────────────────────────
# Package endpoints
# ──────────────────────────────────────────────────────────────────────


@router.post(
    "/packages",
    status_code=201,
    responses={
        400: {"description": "File must be a .stck archive"},
        413: {"description": "Package exceeds maximum upload size"},
    },
)
async def upload_package(
    file: UploadFile,
    player: PlayerDep,
    storage: StorageDep,
) -> JSONResponse:
    """Upload a .stck archive."""
    if not file.filename or not file.filename.endswith(".stck"):
        raise HTTPException(400, "File must be a .stck archive")

    data = await file.read()
    max_bytes = player._config.max_upload_bytes
    if len(data) > max_bytes:
        raise HTTPException(413, f"Package exceeds maximum size of {max_bytes} bytes")

    package_id = uuid.uuid4().hex[:12]
    stem = file.filename.rsplit(".", 1)[0]
    parts = stem.rsplit("-", 1)
    name = parts[0] if parts else stem
    version = parts[1] if len(parts) > 1 else "1.0"

    pkg = storage.save(package_id, name, version, data)
    return JSONResponse(content=pkg.model_dump(mode="json"), status_code=201)


@router.get("/packages")
async def list_packages(storage: StorageDep) -> JSONResponse:
    """List all uploaded packages."""
    packages = storage.list_packages()
    return JSONResponse(content=[package.model_dump(mode="json") for package in packages])


@router.delete(
    "/packages/{package_id}",
    status_code=204,
    responses={404: {"description": "Package not found"}},
)
async def delete_package(package_id: str, storage: StorageDep) -> None:
    """Delete a stored package."""
    if not storage.delete(package_id):
        raise HTTPException(404, "Package not found")


# ──────────────────────────────────────────────────────────────────────
# Job / execution endpoints
# ──────────────────────────────────────────────────────────────────────


@router.post(
    "/run/package",
    status_code=202,
    responses={
        400: {"description": "Missing 'package_id' or 'path' in request body"},
        404: {"description": "Package or file not found"},
    },
)
async def run_test(
    request: Request,
    player: PlayerDep,
    storage: StorageDep,
) -> JSONResponse:
    """Execute a TCK from an uploaded package or a YAML path.

    Body: ``{"package_id": "...", "runtime_vars": {...}}``
    or    ``{"path": "...", "runtime_vars": {...}}``
    """
    body = await request.json()

    package_id = body.get("package_id")
    path = body.get("path")
    runtime_vars = body.get("runtime_vars", {})

    if not package_id and not path:
        raise HTTPException(400, "Provide 'package_id' or 'path'")

    if package_id:
        pkg_path = storage.get_path(package_id)
        if pkg_path is None:
            raise HTTPException(404, f"Package '{package_id}' not found")
        target = pkg_path
    else:
        target = Path(path)
        if not target.exists():
            raise HTTPException(404, f"File not found: {path}")

    job = player.jobs.create(target.stem)
    task = asyncio.create_task(_execute_in_background(player, target, runtime_vars))
    _background_tasks.add(task)
    task.add_done_callback(_on_task_done)

    return JSONResponse(
        content={"job_id": job.job_id, "status": job.status.value},
        status_code=202,
    )


async def _execute_in_background(player: TestlabPlayer, target: Path, runtime_vars: dict) -> None:
    """Run the player in the background, catching exceptions."""
    try:
        await player.run(target, runtime_vars=runtime_vars)
    except (RuntimeError, ValueError, OSError) as exc:
        _logger.warning("Background execution failed: %s", exc)


@router.get(
    "/test-execution",
    responses={400: {"description": "Invalid status filter value"}},
)
async def list_jobs(
    player: PlayerDep,
    status: Optional[str] = None,
) -> JSONResponse:
    """List all executions, optionally filtered by status."""
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status.upper())
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    jobs = player.jobs.list_jobs(status=status_filter)
    return JSONResponse(content=[job.model_dump(mode="json") for job in jobs])


@router.get(
    "/test-execution/{job_id}",
    responses={404: {"description": "Job not found"}},
)
async def get_job(job_id: str, player: PlayerDep) -> JSONResponse:
    """Get details for a specific execution."""
    job = player.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return JSONResponse(content=job.model_dump(mode="json"))


@router.post(
    "/test-execution/{job_id}/cancel",
    status_code=200,
    responses={404: {"description": "Job not found"}},
)
async def cancel_job(job_id: str, player: PlayerDep) -> JSONResponse:
    """Cancel a running job."""
    job = player.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    player.jobs.cancel(job_id)
    player.monitor.on_job_cancelled(job_id)
    return JSONResponse(content={"job_id": job_id, "status": "CANCELLED"})


@router.post(
    "/test-execution/{job_id}/pause",
    status_code=200,
    responses={
        404: {"description": "Job not found"},
        409: {"description": "Job is not in RUNNING state"},
    },
)
async def pause_job(job_id: str, player: PlayerDep) -> JSONResponse:
    """Pause a running execution."""
    job = player.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    if job.status != JobStatus.RUNNING:
        raise HTTPException(409, f"Job '{job_id}' is not running (status: {job.status.value})")
    player.jobs.pause(job_id)
    player.monitor.on_job_paused(job_id)
    return JSONResponse(content={"job_id": job_id, "status": "PAUSED"})


@router.post(
    "/test-execution/{job_id}/resume",
    status_code=200,
    responses={
        404: {"description": "Job not found"},
        409: {"description": "Job is not in PAUSED state"},
    },
)
async def resume_job(job_id: str, player: PlayerDep) -> JSONResponse:
    """Resume a paused execution."""
    job = player.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    if job.status != JobStatus.PAUSED:
        raise HTTPException(409, f"Job '{job_id}' is not paused (status: {job.status.value})")
    player.jobs.resume(job_id)
    player.monitor.on_job_resumed(job_id)
    return JSONResponse(content={"job_id": job_id, "status": "RUNNING"})

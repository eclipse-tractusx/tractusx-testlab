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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""JobManager — creation, lookup, state transitions, memory, and events."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from tractusx_testlab.models import Job, JobEvent, JobMemory
from tractusx_testlab.models.primitives.enums import JobStatus


class JobManager:
    """Manages the lifecycle of Job objects."""

    __slots__ = ("_jobs", "_pause_events")

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._pause_events: dict[str, asyncio.Event] = {}

    def create(self, tck_id: str, package_name: str | None = None) -> Job:
        """Create a new job in QUEUED state."""
        job = Job(
            job_id=uuid.uuid4().hex,
            tck_id=tck_id,
            package_name=package_name,
            status=JobStatus.QUEUED,
            created_at=datetime.now(UTC),
            memory=JobMemory(),
        )
        self._jobs[job.job_id] = job
        event = asyncio.Event()
        event.set()  # Not paused by default
        self._pause_events[job.job_id] = event
        return job

    def get(self, job_id: str) -> Job | None:
        """Return a job by ID, or None if not found."""
        return self._jobs.get(job_id)

    def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """Return jobs optionally filtered by status with pagination."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [job for job in jobs if job.status == status]
        return jobs[offset : offset + limit]

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def start(self, job_id: str) -> None:
        """Transition a job to RUNNING state."""
        job = self._require(job_id)
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        self._event(job, "lifecycle", "Job started")

    def complete(self, job_id: str) -> None:
        """Mark a job as successfully completed."""
        job = self._require(job_id)
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        self._event(job, "lifecycle", "Job completed")

    def fail(self, job_id: str, reason: str = "") -> None:
        """Mark a job as failed with an optional reason."""
        job = self._require(job_id)
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(UTC)
        job.error = reason or None
        self._event(job, "lifecycle", f"Job failed: {reason}" if reason else "Job failed")

    def wait(self, job_id: str, step_name: str, listener_url: str) -> None:
        """Transition a job to WAITING state pending an external callback."""
        job = self._require(job_id)
        job.status = JobStatus.WAITING
        job.waiting_for = listener_url
        job.current_step = step_name
        self._event(job, "waiting", f"Waiting for callback at step {step_name}")

    def resume(self, job_id: str) -> Job:
        """Resume a WAITING or PAUSED job back to RUNNING."""
        job = self._require(job_id)
        if job.status == JobStatus.WAITING:
            job.status = JobStatus.RUNNING
            job.waiting_for = None
            self._event(job, "lifecycle", "Job resumed from WAITING")
        elif job.status == JobStatus.PAUSED:
            job.status = JobStatus.RUNNING
            self._pause_events[job_id].set()
            self._event(job, "lifecycle", "Job resumed from PAUSED")
        return job

    def get_pause_event(self, job_id: str) -> asyncio.Event:
        """Return the pause gate for *job_id*. ``await event.wait()`` blocks while paused."""
        event = self._pause_events.get(job_id)
        if event is None:
            event = asyncio.Event()
            event.set()
            self._pause_events[job_id] = event
        return event

    def pause(self, job_id: str) -> Job:
        """Pause a RUNNING job. Blocks the execution loop until resumed."""
        job = self._require(job_id)
        if job.status != JobStatus.RUNNING:
            raise ValueError(f"Cannot pause job '{job_id}' in state {job.status.value}")
        job.status = JobStatus.PAUSED
        self._pause_events[job_id].clear()
        self._event(job, "lifecycle", "Job paused")
        return job

    def cancel(self, job_id: str) -> None:
        """Cancel a job if it has not already reached a terminal state."""
        job = self._require(job_id)
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return
        if job.status == JobStatus.PAUSED:
            self._pause_events[job_id].set()  # Unblock execution loop
        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.now(UTC)
        self._event(job, "lifecycle", "Job cancelled")

    def set_current_step(self, job_id: str, step_name: str) -> None:
        """Update the current step name for progress tracking."""
        job = self._require(job_id)
        job.current_step = step_name

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job '{job_id}' not found")
        return job

    @staticmethod
    def _event(job: Job, event_type: str, description: str) -> None:
        job.memory.log_event(
            JobEvent(
                timestamp=datetime.now(UTC),
                event_type=event_type,
                description=description,
            )
        )

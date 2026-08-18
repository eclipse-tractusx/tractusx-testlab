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

"""Job models — execution-time structures for job tracking and memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from tractusx_testlab.models.primitives.enums import JobStatus
from tractusx_testlab.models.runtime.results import TckResult as TckResult  # SDK alias


class JobEvent(BaseModel):
    """Record of a single event during job execution."""

    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str = ""
    description: str = ""
    data: dict | None = None


class JobMemory(BaseModel):
    """Mutable key-value store and event log attached to a running job."""

    state: dict[str, Any] = Field(default_factory=dict)
    events: list[JobEvent] = Field(default_factory=list)

    def set(self, key: str, value: Any) -> None:
        """Store a value in job memory."""
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from job memory, returning default if absent."""
        return self.state.get(key, default)

    def has(self, key: str) -> bool:
        """Check whether a key exists in job memory."""
        return key in self.state

    def log_event(self, event: JobEvent) -> None:
        """Append an event to the job event log."""
        self.events.append(event)


class Job(BaseModel):
    """Runtime representation of a test execution job."""

    job_id: str
    status: JobStatus = JobStatus.QUEUED
    package_name: str | None = None
    tck_id: str | None = None
    runtime_vars: dict = Field(default_factory=dict)
    memory: JobMemory = Field(default_factory=JobMemory)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_duration_s: float | None = None
    current_script: str | None = None
    current_step: str | None = None
    waiting_for: str | None = None
    result: TckResult | None = None
    error: str | None = None

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

"""In-memory SSE event buffer for replay on client reconnect."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BufferedEvent:
    """A single SSE event stored for replay."""

    id: int
    event: str
    data: dict[str, Any]


class EventBuffer:
    """Per-job ring buffer of recent SSE events for reconnect replay.

    Stores the last *max_per_job* events per job and provides monotonically
    increasing event IDs for SSE ``id:`` fields.
    """

    __slots__ = ("_buffers", "_counters", "_max_per_job")

    def __init__(self, max_per_job: int = 100) -> None:
        self._buffers: dict[str, list[BufferedEvent]] = {}
        self._counters: dict[str, int] = {}
        self._max_per_job = max_per_job

    def next_id(self, job_id: str) -> int:
        """Return the next monotonic event ID for *job_id*."""
        self._counters[job_id] = self._counters.get(job_id, 0) + 1
        return self._counters[job_id]

    def append(self, job_id: str, event: BufferedEvent) -> None:
        """Append an event to the buffer, evicting oldest if full."""
        buf = self._buffers.setdefault(job_id, [])
        buf.append(event)
        if len(buf) > self._max_per_job:
            self._buffers[job_id] = buf[-self._max_per_job :]

    def get_events_after(self, job_id: str, last_id: int) -> list[BufferedEvent]:
        """Return all buffered events with ID > *last_id*."""
        return [e for e in self._buffers.get(job_id, []) if e.id > last_id]

    def clear(self, job_id: str) -> None:
        """Remove all buffered events and reset counter for *job_id*."""
        self._buffers.pop(job_id, None)
        self._counters.pop(job_id, None)

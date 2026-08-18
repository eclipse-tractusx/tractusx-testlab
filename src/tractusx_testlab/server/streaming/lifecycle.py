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

"""SSE connection lifecycle — queue creation, replay, keepalive, and timeout."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.server.streaming._event_buffer import BufferedEvent, EventBuffer
from tractusx_testlab.server.streaming.formatter import TERMINAL_EVENTS, format_sse

_logger = logging.getLogger(__name__)


def create_event_queue(monitor: ExecutionMonitor) -> asyncio.Queue[tuple[str, dict[str, Any]]]:
    """Register a callback on *monitor* that pushes events into a queue.

    Returns the queue. The callback is sync-safe (uses ``put_nowait``).
    """
    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

    def _push_event(event: str, payload: dict[str, Any]) -> None:
        queue.put_nowait((event, payload))

    monitor.add_callback(_push_event)
    return queue


async def sse_event_generator(
    queue: asyncio.Queue[tuple[str, dict[str, Any]]],
    job_id: str,
    event_buffer: EventBuffer,
    last_event_id: int | None = None,
    timeout_s: float = 600.0,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings from *queue* until a terminal event arrives.

    Features:
        - **Replay**: If *last_event_id* is set, replays buffered events first.
        - **Heartbeat**: Sends ``:keepalive`` comment every 15 s when idle.
        - **Event IDs**: Every event includes a monotonic ``id:`` field.
        - **Buffer**: Events are stored for future replay on reconnect.

    Args:
        queue: Event queue populated by :func:`create_event_queue`.
        job_id: Job identifier for buffer scoping.
        event_buffer: Shared event buffer instance.
        last_event_id: If set, replay events with ID > this value.
        timeout_s: Maximum seconds without a *real* event before closing.
    """
    # Phase 1: replay buffered events
    if last_event_id is not None:
        for buffered in event_buffer.get_events_after(job_id, last_event_id):
            yield format_sse(buffered.id, buffered.event, buffered.data)

    # Phase 2: live stream with heartbeat
    last_real_event = time.monotonic()
    try:
        while True:
            try:
                event, payload = await asyncio.wait_for(queue.get(), timeout=15.0)
            except TimeoutError:
                if time.monotonic() - last_real_event > timeout_s:
                    event_id = event_buffer.next_id(job_id)
                    timeout_data = {"reason": "No events received within timeout"}
                    event_buffer.append(
                        job_id,
                        BufferedEvent(id=event_id, event="stream.timeout", data=timeout_data),
                    )
                    yield format_sse(event_id, "stream.timeout", timeout_data)
                    return
                yield ":keepalive\n\n"
                continue

            last_real_event = time.monotonic()
            event_id = event_buffer.next_id(job_id)
            event_buffer.append(job_id, BufferedEvent(id=event_id, event=event, data=payload))
            yield format_sse(event_id, event, payload)

            if event in TERMINAL_EVENTS:
                return
    except asyncio.CancelledError:
        _logger.debug("SSE stream cancelled by client disconnect")
        raise

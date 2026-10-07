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

"""SSE wire formatting — converts events to the text/event-stream format."""

from __future__ import annotations

import json
from typing import Any

TERMINAL_EVENTS = frozenset({"job.completed", "job.failed", "job.cancelled"})


def format_sse(event_id: int, event: str, data: dict[str, Any]) -> str:
    """Format a single SSE message with an ``id:`` field."""
    payload = json.dumps(data, default=str)
    return f"id: {event_id}\nevent: {event}\ndata: {payload}\n\n"

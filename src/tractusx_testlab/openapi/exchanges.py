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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The API calls a test made, kept for the checks that look across them.

``labs/validate/api_errors`` judges a test's error answers together — one
format, no leaks, no 5xx for a request sent wrong on purpose — so every API
call step notes its answer here. The journal belongs to one test: the runner
clears it when the next begins.

It is bounded twice: at most :data:`MAX_EXCHANGES` answers, the oldest dropped
first, and only an error answer keeps its body, clipped to
:data:`MAX_BODY_CHARS` — a success body is never read across steps.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MAX_EXCHANGES = 256
MAX_BODY_CHARS = 64 * 1024


@dataclass(frozen=True, slots=True)
class ApiExchange:
    """One answer an API call step received."""

    step: str | None
    api: str
    operation: str
    status: int
    headers: Mapping[str, str]
    #: The body of an error answer, clipped; ``None`` for any other.
    body: Any
    expect: int | str | None = None


class ApiExchangeJournal:
    """The API answers of the running test, oldest first."""

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: deque[ApiExchange] = deque(maxlen=MAX_EXCHANGES)

    def note(
        self,
        *,
        step: str | None,
        api: str,
        operation: str,
        status: int,
        headers: Mapping[str, str],
        body: Any,
        expect: int | str | None = None,
    ) -> None:
        kept = _clipped(body) if status >= 400 else None
        self._entries.append(ApiExchange(step, api, operation, status, dict(headers), kept, expect))

    def entries(self) -> list[ApiExchange]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()


def _clipped(body: Any) -> Any:
    if isinstance(body, str):
        return body[:MAX_BODY_CHARS]
    try:
        size = len(json.dumps(body, default=str))
    except (TypeError, ValueError):
        return str(body)[:MAX_BODY_CHARS]
    return body if size <= MAX_BODY_CHARS else json.dumps(body, default=str)[:MAX_BODY_CHARS]

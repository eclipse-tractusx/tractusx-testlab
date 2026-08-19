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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The execution trace — one CloudEvents v1.0 line per thing that happened.

ADR-0016. This is the machine-readable record of a run: what the IDE streams
over SSE, what the report is rebuilt from, and what an operator reads to find
out why a step failed. It is written to ``data_dir``, deliberately apart from
``logs_dir`` — the log is the console transcript a person reads, the trace is
the evidence a tool parses, and one file cannot be both without one of the two
audiences losing.

Every line is a self-contained CloudEvent::

    {
        "specversion": "1.0",
        "id": "<path>/<type>/<hash>",
        "source": "<uses>",
        "type": "tck.test.step.failed",
        "time": "...",
        "sequence": 7,
        "data": {...},
    }

The ``id`` encodes structural context as path segments so an event says where
it belongs without the reader tracking state across lines; the trailing 12-hex
blake2b of ``data`` disambiguates two emissions with the same path — the second
attempt of a retried step, most often.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

#: CloudEvents spec version every line declares.
SPEC_VERSION = "1.0"

#: ``source`` for events the player emits about itself rather than about a step.
SOURCE_LIFECYCLE = "testlab/player/lifecycle"
SOURCE_BOOT = "testlab/player/boot"
SOURCE_VARIABLES = "testlab/player/variables"


def _digest(data: Any) -> str:
    """A 12-hex fingerprint of an event's payload.

    Keyed on the payload rather than on a counter so the same event re-derived
    from the same run gets the same id — the trace is meant to be an audit
    record, and an id that changes per read is not one.
    """
    encoded = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.blake2b(encoded.encode("utf-8"), digest_size=6).hexdigest()


class ExecutionTrace:
    """Writes one run's CloudEvents to ``<data_dir>/<date>/<time>_<job_id>.jsonl``.

    The sequence counter is global to the run and 1-based, which is what makes
    SSE ``Last-Event-ID`` resumption possible: a reconnecting IDE names the last
    sequence it saw and the backend continues from the next one.

    A trace with no ``data_dir`` still counts and still renders events — it just
    writes nowhere. That keeps the emitting code free of ``if trace is not None``
    at every call site.
    """

    __slots__ = ("_handle", "_lock", "_path", "_sequence", "_tck_id")

    def __init__(self, tck_id: str, path: Path | None = None) -> None:
        self._tck_id = tck_id or "tck"
        self._path = path
        self._sequence = 0
        self._lock = threading.Lock()
        self._handle: IO[str] | None = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = path.open("a", encoding="utf-8")

    @classmethod
    def for_job(cls, tck_id: str, job_id: str, data_dir: Path | None) -> ExecutionTrace:
        """Open the trace file for one job, named so runs sort chronologically."""
        if data_dir is None:
            return cls(tck_id)
        now = datetime.now(UTC)
        time_prefix = now.strftime("%H-%M-%S-") + f"{now.microsecond // 1000:03d}"
        return cls(
            tck_id,
            data_dir / now.strftime("%Y-%m-%d") / f"{time_prefix}_{job_id}.jsonl",
        )

    @property
    def path(self) -> Path | None:
        """Where this trace is being written, or ``None`` when it is not."""
        return self._path

    @property
    def tck_id(self) -> str:
        return self._tck_id

    def emit(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        source: str = SOURCE_LIFECYCLE,
        scope: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Write one CloudEvent and return it.

        *scope* is the path between the TCK id and the event type — the test id,
        then the step id, or ``("infrastructure", "engine.connector")`` for a
        boot event. The returned envelope is what the SSE transport frames.
        """
        payload = _jsonable(data)
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            envelope = {
                "specversion": SPEC_VERSION,
                "id": "/".join((self._tck_id, *scope, event_type, _digest(payload))),
                "source": source,
                "type": event_type,
                "time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "sequence": sequence,
                "data": payload,
            }
            if self._handle is not None:
                self._handle.write(json.dumps(envelope, default=str, separators=(",", ":")) + "\n")
                self._handle.flush()
        return envelope

    def close(self) -> None:
        with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None


def _jsonable(value: Any) -> Any:
    """Coerce pydantic models, enums and datetimes into plain JSON types."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value

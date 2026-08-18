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

"""ParticipantManager — protocol and filesystem implementation for test participants."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

_BPNL_PREFIX = "BPNL"
_BPNL_BODY_LENGTH = 12
_BPNL_CHECK_LENGTH = 2
_BPNL_TOTAL_LENGTH = len(_BPNL_PREFIX) + _BPNL_BODY_LENGTH + _BPNL_CHECK_LENGTH
_BPNL_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_STORAGE_VERSION = "1.0"
_STORAGE_FILENAME = "participants.json"


class Participant(BaseModel):
    """A test participant with a deterministic BPNL."""

    model_config = ConfigDict(frozen=True)

    name: str
    bpnl: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class ParticipantManager(Protocol):
    """Abstract manager for test participant identities."""

    def get_or_create(self, name: str) -> Participant: ...

    def get(self, name: str) -> Participant | None: ...

    def list_all(self) -> list[Participant]: ...


class FileSystemParticipantManager:
    """Stores participants as JSON in a config directory.

    Thread-safe for single-process usage.  Reads once at init, writes
    on every mutation to keep the file consistent.
    """

    __slots__ = ("_participants", "_storage_path")

    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path
        self._participants: dict[str, Participant] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_or_create(self, name: str) -> Participant:
        """Return existing participant or create a new one with a deterministic BPNL."""
        if not name or not name.strip():
            raise ValueError("Participant name must not be empty")

        normalised = name.strip()
        if normalised in self._participants:
            return self._participants[normalised]

        participant = Participant(
            name=normalised,
            bpnl=_generate_bpnl(normalised),
            created_at=datetime.now(UTC),
        )
        self._participants[normalised] = participant
        self._save()
        logger.info("Created participant '%s' with BPNL %s", normalised, participant.bpnl)
        return participant

    def get(self, name: str) -> Participant | None:
        """Return a participant by name, or ``None`` if unknown."""
        return self._participants.get(name.strip() if name else name)

    def list_all(self) -> list[Participant]:
        """Return all registered participants."""
        return list(self._participants.values())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        file_path = self._storage_path / _STORAGE_FILENAME
        if not file_path.exists():
            logger.debug("No participant file at %s — starting fresh", file_path)
            return

        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load participants from %s: %s", file_path, exc)
            return

        for entry in raw.get("participants", {}).values():
            participant = Participant.model_validate(entry)
            self._participants[participant.name] = participant

        logger.debug("Loaded %d participants from %s", len(self._participants), file_path)

    def _save(self) -> None:
        self._storage_path.mkdir(parents=True, exist_ok=True)
        file_path = self._storage_path / _STORAGE_FILENAME

        payload = {
            "version": _STORAGE_VERSION,
            "participants": {
                name: p.model_dump(mode="json") for name, p in self._participants.items()
            },
        }
        file_path.write_text(
            json.dumps(payload, indent=2, default=str) + "\n",
            encoding="utf-8",
        )


# ------------------------------------------------------------------
# BPNL generation (private)
# ------------------------------------------------------------------


def _generate_bpnl(name: str) -> str:
    """Generate a deterministic BPNL from a participant name.

    Format: ``BPNL`` + 12 alphanumeric chars (from SHA-256) + 2 check chars.
    The same *name* always produces the same BPNL.
    """
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest().upper()

    body_chars: list[str] = []
    for ch in digest:
        if ch in _BPNL_ALPHABET:
            body_chars.append(ch)
        if len(body_chars) == _BPNL_BODY_LENGTH:
            break

    # Pad with '0' if the digest somehow didn't yield enough (shouldn't happen for SHA-256)
    while len(body_chars) < _BPNL_BODY_LENGTH:
        body_chars.append("0")  # pragma: no cover

    body = "".join(body_chars)
    check = _compute_check_chars(body)
    return f"{_BPNL_PREFIX}{body}{check}"


def _compute_check_chars(body: str) -> str:
    """Compute 2 check characters from the body using a simple modular hash."""
    hash_val = int(hashlib.sha256(body.encode("utf-8")).hexdigest(), 16)
    c1 = _BPNL_ALPHABET[hash_val % len(_BPNL_ALPHABET)]
    c2 = _BPNL_ALPHABET[(hash_val // len(_BPNL_ALPHABET)) % len(_BPNL_ALPHABET)]
    return f"{c1}{c2}"

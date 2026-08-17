#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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

"""Tests for ParticipantManager — BPNL generation, persistence, edge cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tractusx_testlab.services.participants import (
    FileSystemParticipantManager,
    Participant,
    _generate_bpnl,
)


# ---------------------------------------------------------------------------
# BPNL format and determinism
# ---------------------------------------------------------------------------


class TestBpnlFormat:
    def test_starts_with_prefix(self) -> None:
        assert _generate_bpnl("acme-corp").startswith("BPNL")

    def test_correct_length(self) -> None:
        assert len(_generate_bpnl("acme-corp")) == 18

    def test_body_is_uppercase_alphanumeric(self) -> None:
        body = _generate_bpnl("acme-corp")[4:]
        assert body.isalnum()
        assert body == body.upper()

    def test_deterministic_same_name(self) -> None:
        assert _generate_bpnl("provider-x") == _generate_bpnl("provider-x")

    def test_different_names_produce_different_bpnls(self) -> None:
        assert _generate_bpnl("company-a") != _generate_bpnl("company-b")

    def test_unicode_name_produces_valid_bpnl(self) -> None:
        bpnl = _generate_bpnl("Ünternehmen-ÄÖÜ")
        assert bpnl.startswith("BPNL")
        assert len(bpnl) == 18

    def test_long_name_produces_valid_bpnl(self) -> None:
        bpnl = _generate_bpnl("a" * 500)
        assert len(bpnl) == 18


# ---------------------------------------------------------------------------
# FileSystemParticipantManager — core operations
# ---------------------------------------------------------------------------


class TestParticipantManagerCore:
    def test_get_or_create_returns_participant(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        p = participant_manager.get_or_create("Alpha Corp")
        assert isinstance(p, Participant)
        assert p.name == "Alpha Corp"
        assert p.bpnl.startswith("BPNL")

    def test_get_or_create_is_idempotent(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        p1 = participant_manager.get_or_create("Repeat Inc")
        p2 = participant_manager.get_or_create("Repeat Inc")
        assert p1 == p2

    def test_get_returns_none_for_unknown(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        assert participant_manager.get("ghost") is None

    def test_get_returns_existing(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        created = participant_manager.get_or_create("Findable")
        assert participant_manager.get("Findable") == created

    def test_empty_name_raises(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            participant_manager.get_or_create("")

    def test_whitespace_only_name_raises(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            participant_manager.get_or_create("   ")

    def test_strips_leading_trailing_whitespace(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        p = participant_manager.get_or_create("  Trimmed  ")
        assert p.name == "Trimmed"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestParticipantManagerPersistence:
    def test_new_instance_finds_existing(
        self, tmp_participants_dir: Path,
    ) -> None:
        mgr1 = FileSystemParticipantManager(tmp_participants_dir)
        mgr1.get_or_create("Persisted Co")

        mgr2 = FileSystemParticipantManager(tmp_participants_dir)
        assert mgr2.get("Persisted Co") is not None

    def test_storage_file_is_valid_json(
        self, tmp_participants_dir: Path,
        participant_manager: FileSystemParticipantManager,
    ) -> None:
        participant_manager.get_or_create("JSON Check")
        raw = json.loads(
            (tmp_participants_dir / "participants.json").read_text(encoding="utf-8"),
        )
        assert raw["version"] == "1.0"
        assert "JSON Check" in raw["participants"]

    def test_multiple_participants_stored_and_retrievable(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        names = ["Alpha", "Bravo", "Charlie"]
        for name in names:
            participant_manager.get_or_create(name)

        all_p = participant_manager.list_all()
        assert len(all_p) == 3
        stored_names = {p.name for p in all_p}
        assert stored_names == set(names)


# ---------------------------------------------------------------------------
# Participant model
# ---------------------------------------------------------------------------


class TestParticipantModel:
    def test_participant_is_frozen(
        self, participant_manager: FileSystemParticipantManager,
    ) -> None:
        p = participant_manager.get_or_create("Frozen Corp")
        with pytest.raises(Exception):
            p.name = "Changed"  # type: ignore[misc]

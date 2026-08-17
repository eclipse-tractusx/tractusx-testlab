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

"""Tests for ParticipantManager — protocol, filesystem implementation, BPNL generation."""

from __future__ import annotations

import json

import pytest

from tractusx_testlab.services.participants import (
    FileSystemParticipantManager,
    Participant,
    ParticipantManager,
    _generate_bpnl,
)


class TestBpnlGeneration:
    """BPNL format and determinism."""

    def test_bpnl_has_correct_length(self) -> None:
        bpnl = _generate_bpnl("test-company")
        assert len(bpnl) == 18

    def test_bpnl_starts_with_prefix(self) -> None:
        bpnl = _generate_bpnl("provider-a")
        assert bpnl.startswith("BPNL")

    def test_bpnl_is_deterministic(self) -> None:
        assert _generate_bpnl("same-name") == _generate_bpnl("same-name")

    def test_bpnl_differs_for_different_names(self) -> None:
        assert _generate_bpnl("company-a") != _generate_bpnl("company-b")

    def test_bpnl_is_uppercase_alphanumeric(self) -> None:
        bpnl = _generate_bpnl("another-company")
        body = bpnl[4:]  # strip BPNL prefix
        assert body.isalnum()
        assert body == body.upper()


class TestFileSystemParticipantManager:
    """Filesystem-backed participant manager."""

    def test_get_or_create_returns_participant(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        p = mgr.get_or_create("Provider A")
        assert isinstance(p, Participant)
        assert p.name == "Provider A"
        assert p.bpnl.startswith("BPNL")
        assert len(p.bpnl) == 18

    def test_get_or_create_is_idempotent(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        p1 = mgr.get_or_create("Company X")
        p2 = mgr.get_or_create("Company X")
        assert p1 == p2

    def test_get_unknown_returns_none(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        assert mgr.get("nonexistent") is None

    def test_get_returns_existing(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        created = mgr.get_or_create("Found Me")
        fetched = mgr.get("Found Me")
        assert fetched == created

    def test_empty_name_raises_value_error(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.get_or_create("")

    def test_whitespace_name_raises_value_error(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.get_or_create("   ")

    def test_persists_to_disk(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        mgr.get_or_create("Persisted Corp")

        # New manager instance reads from disk
        mgr2 = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        p = mgr2.get("Persisted Corp")
        assert p is not None
        assert p.name == "Persisted Corp"

    def test_storage_file_format(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        mgr.get_or_create("Format Check")

        raw = json.loads((tmp_path / "participants.json").read_text())  # type: ignore[operator]
        assert raw["version"] == "1.0"
        assert "Format Check" in raw["participants"]
        entry = raw["participants"]["Format Check"]
        assert entry["name"] == "Format Check"
        assert entry["bpnl"].startswith("BPNL")

    def test_list_all(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        mgr.get_or_create("A")
        mgr.get_or_create("B")
        assert len(mgr.list_all()) == 2

    def test_strips_whitespace_from_name(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        p = mgr.get_or_create("  Spacey  ")
        assert p.name == "Spacey"


class TestProtocolCompliance:
    """FileSystemParticipantManager satisfies the ParticipantManager protocol."""

    def test_implements_protocol(self, tmp_path: object) -> None:
        mgr = FileSystemParticipantManager(tmp_path)  # type: ignore[arg-type]
        assert isinstance(mgr, ParticipantManager)

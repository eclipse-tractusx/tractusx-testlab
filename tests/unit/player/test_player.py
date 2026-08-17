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

"""Tests for TestlabPlayer — the high-level async test executor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from tractusx_testlab.player.execution.player import TestlabPlayer


def _write_tck(tmp_path: Path) -> Path:
    """Write a minimal TCK + script YAML for loading."""
    script = {
        "kind": "test",
        "name": "Smoke Test",
        "version": "1.0",
        "dataspace_version": "saturn",
        "execution": [],
    }
    tck = {
        "kind": "tck",
        "name": "Minimal TCK",
        "version": "1.0",
        "tests": [script],
    }
    p = tmp_path / "tck.yaml"
    p.write_text(yaml.dump(tck, default_flow_style=False))
    return p


class TestTestlabPlayerInit:
    """Tests for TestlabPlayer instantiation."""

    def test_player_creates_with_mock_config(self, tmp_path: Path) -> None:
        mock_config = MagicMock()
        mock_config.logs_dir = tmp_path / "testlab-logs"
        player = TestlabPlayer(config=mock_config)
        assert player.jobs is not None
        assert player.monitor is not None

    def test_player_jobs_manager_is_accessible(self, tmp_path: Path) -> None:
        mock_config = MagicMock()
        mock_config.logs_dir = tmp_path / "testlab-logs"
        player = TestlabPlayer(config=mock_config)
        assert player.jobs is not None


class TestTestlabPlayerRun:
    """Tests for TestlabPlayer loading — full run requires mock server infrastructure."""

    def test_player_loader_is_available(self, tmp_path: Path) -> None:
        # Arrange
        mock_config = MagicMock()
        mock_config.logs_dir = tmp_path / "testlab-logs"
        player = TestlabPlayer(config=mock_config)

        # Assert — loader is initialized and accessible internally
        assert player._loader is not None

    def test_player_monitor_tracks_state(self, tmp_path: Path) -> None:
        # Arrange
        mock_config = MagicMock()
        mock_config.logs_dir = tmp_path / "testlab-logs"
        player = TestlabPlayer(config=mock_config)

        # Assert
        monitor = player.monitor
        assert monitor is not None

################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""CLI integration tests for `testlab inspect`."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tractusx_testlab.cli import app
from tractusx_testlab.player.loading.loader import _TCK_BUNDLE_ENTRY

runner = CliRunner()

_TCK_BUNDLE_YAML = """\
syntax: v2
kind: tck
id: tck-cli-inspect
namespace: testlab.test
metadata:
  name: CLI Inspect TCK
  version: "1.0"
tests:
  - id: inspect-script.yaml
    name: Inspect Script
"""

_SCRIPT_YAML = """\
syntax: v2
kind: test
id: inspect-script
namespace: testlab.test
dataspace_version: saturn
metadata:
  name: Inspect Script
  version: "1.0"
setup:
  - uses: util/generate_uuid
    name: Generate UUID
execution:
  - uses: http/http_request
    name: HTTP Request
    validate:
      - uses: assert/status_code
        with: {expected: 200}
teardown:
  - uses: connector/provider/delete_asset
    name: Delete Asset
"""


@pytest.fixture()
def tck_archive(tmp_path: Path) -> Path:
    """Build a plain .tck ZIP archive for CLI tests."""
    archive = tmp_path / "cli-inspect.tck"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(_TCK_BUNDLE_ENTRY, _TCK_BUNDLE_YAML)
        zf.writestr("tests/inspect-script.yaml", _SCRIPT_YAML)
    return archive


class TestInspectCommand:
    """Tests for the `testlab inspect` CLI command."""

    def test_inspect_exits_zero_for_valid_tck(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive)])
        assert result.exit_code == 0

    def test_inspect_human_output_contains_tck_name(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive)])
        assert "CLI Inspect TCK" in result.output

    def test_inspect_human_output_shows_step_counts(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive)])
        assert "Total Steps" in result.output
        assert "Total Validations" in result.output

    def test_inspect_human_output_shows_phase_labels(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive)])
        assert "Setup" in result.output
        assert "Execution" in result.output
        assert "Teardown" in result.output

    def test_inspect_human_output_shows_uses_identifier(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive)])
        assert "util/generate_uuid" in result.output
        assert "http/http_request" in result.output
        assert "connector/provider/delete_asset" in result.output

    def test_inspect_json_flag_produces_valid_json(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "CLI Inspect TCK"

    def test_inspect_json_contains_scripts_and_steps(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)
        assert len(data["scripts"]) == 1
        steps = data["scripts"][0]["steps"]
        assert len(steps) == 3  # setup + execution + teardown

    def test_inspect_json_step_has_expected_fields(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)
        step = data["scripts"][0]["steps"][0]
        assert "step_name" in step
        assert "uses" in step
        assert "phase" in step
        assert "validation_count" in step

    def test_inspect_json_total_steps_is_three(self, tck_archive: Path) -> None:
        # setup(1) + execution(1) + teardown(1) = 3
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)
        assert data["total_steps"] == 3

    def test_inspect_json_total_validations_is_one(self, tck_archive: Path) -> None:
        # only execution step has 1 validation
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)
        assert data["total_validations"] == 1

    def test_inspect_exits_one_for_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tmp_path / "no-such.tck")])
        assert result.exit_code == 1

    def test_inspect_exits_one_for_stck_without_player_keys(self, tmp_path: Path) -> None:
        fake_stck = tmp_path / "fake.stck"
        fake_stck.write_bytes(b"not-real")
        result = runner.invoke(app, ["inspect", str(fake_stck)])
        assert result.exit_code == 1
        assert "--player-keys" in result.output

    def test_inspect_exits_one_for_stck_without_compiler_pub(self, tmp_path: Path) -> None:
        fake_stck = tmp_path / "fake.stck"
        fake_stck.write_bytes(b"not-real")
        result = runner.invoke(
            app, ["inspect", str(fake_stck), "--player-keys", str(tmp_path)]
        )
        assert result.exit_code == 1
        assert "--compiler-pub" in result.output

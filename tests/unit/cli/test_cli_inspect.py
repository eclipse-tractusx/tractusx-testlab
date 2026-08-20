################################################################################
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
from tractusx_testlab.compiler import package_digest
from tractusx_testlab.player.loading.loader import _TCK_BUNDLE_ENTRY

runner = CliRunner()

_TCK_BUNDLE_YAML = """\
syntax: v1-alpha
kind: tck
id: tck-cli-inspect
metadata:
  name: CLI Inspect TCK
  version: "1.0"
tests:
  - id: inspect-script.yaml
    name: Inspect Script
"""

_SCRIPT_YAML = """\
syntax: v1-alpha
kind: test
id: inspect-script
namespace: testlab.test
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
      - uses: validate/assert/equals
        with: {input: status_code, value: 200}
teardown:
  - uses: connector/provider/delete_asset
    name: Delete Asset
"""


def _write_sealed(archive: Path, entries: dict[str, bytes]) -> None:
    """Write a ``.tck`` sealed the way the compiler seals one.

    Goes through :func:`package_digest.seal`, the same function the compiler
    uses, so a fixture is by construction a package the loader will accept — a
    test cannot pass against a sealing rule that exists only in the test.
    """
    sealed = package_digest.seal({"manifest.yaml": b"kind: manifest\n", **entries})
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(sealed):
            zf.writestr(name, sealed[name])


@pytest.fixture()
def tck_archive(tmp_path: Path) -> Path:
    """Build a plain .tck ZIP archive for CLI tests."""
    archive = tmp_path / "cli-inspect.tck"
    _write_sealed(
        archive,
        {
            _TCK_BUNDLE_ENTRY: _TCK_BUNDLE_YAML.encode(),
            "tests/inspect-script.yaml": _SCRIPT_YAML.encode(),
        },
    )
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
        # Always an envelope keyed by section, whichever flags were passed.
        assert data["inspection"]["name"] == "CLI Inspect TCK"

    def test_inspect_json_contains_scripts_and_steps(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)["inspection"]
        assert len(data["scripts"]) == 1
        steps = data["scripts"][0]["steps"]
        assert len(steps) == 3  # setup + execution + teardown

    def test_inspect_json_step_has_expected_fields(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)["inspection"]
        step = data["scripts"][0]["steps"][0]
        assert "step_name" in step
        assert "uses" in step
        assert "phase" in step
        assert "validation_count" in step

    def test_inspect_json_total_steps_is_three(self, tck_archive: Path) -> None:
        # setup(1) + execution(1) + teardown(1) = 3
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)["inspection"]
        assert data["total_steps"] == 3

    def test_inspect_json_total_validations_is_one(self, tck_archive: Path) -> None:
        # only execution step has 1 validation
        result = runner.invoke(app, ["inspect", str(tck_archive), "--json"])
        data = json.loads(result.output)["inspection"]
        assert data["total_validations"] == 1

    def test_inspect_exits_one_for_missing_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tmp_path / "no-such.tck")])
        assert result.exit_code == 1

    def test_inspect_exits_one_for_a_file_that_is_not_an_archive(self, tmp_path: Path) -> None:
        not_a_package = tmp_path / "fake.tck"
        not_a_package.write_bytes(b"not-real")
        result = runner.invoke(app, ["inspect", str(not_a_package)])
        assert result.exit_code == 1
        assert "Refused to inspect" in result.output

    def test_inspect_prints_the_manifest(self, tck_archive: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tck_archive), "--manifest"])
        assert result.exit_code == 0
        assert "MANIFEST" in result.output
        assert "Checksum" in result.output

    def test_inspect_manifest_as_json(self, tck_archive: Path) -> None:
        """What ``compile info`` printed, now a section of one command."""
        result = runner.invoke(app, ["inspect", str(tck_archive), "--manifest", "--json"])
        assert result.exit_code == 0
        assert "checksum" in json.loads(result.output)["manifest"]["package"]

    def test_inspect_extracts_the_verified_contents(
        self, tck_archive: Path, tmp_path: Path
    ) -> None:
        """What ``compile decompile`` did — for every entry, not one YAML."""
        out = tmp_path / "extracted"
        result = runner.invoke(app, ["inspect", str(tck_archive), "--extract", str(out)])
        assert result.exit_code == 0
        written = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
        assert "manifest.yaml" in written
        assert "tck-bundle.yaml" in written

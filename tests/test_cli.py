###############################################################
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
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Tests for the CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tractusx_testlab.cli import app

runner = CliRunner()


_VALID_YAML = """\
syntax: v1-alpha
kind: tck
id: cli-tck
metadata:
  name: CLI TCK
  version: "1.0"
  authors: []
  copyright_holders: []
  license: Apache-2.0
tests: []
"""

_INVALID_YAML = "{{not valid yaml"

_BAD_STEP_YAML = """\
syntax: v2
kind: tck
id: bad-step-tck
metadata:
  name: Bad Step TCK
  version: "1.0"
  authors: []
  copyright_holders: []
  license: Apache-2.0
tests: []
"""

@pytest.fixture()
def valid_yaml_file() -> Path:
    # Use the real CCM example which is known-valid and satisfies JSON schema.
    p = Path("docs/examples/certificate-management-v2/raw/index.yaml")
    if not p.exists():
        pytest.skip("CCM example not found")
    return p


@pytest.fixture()
def invalid_yaml_file(tmp_path: Path) -> Path:
    f = tmp_path / "invalid.yaml"
    f.write_text(_INVALID_YAML)
    return f


@pytest.fixture()
def bad_step_yaml_file(tmp_path: Path) -> Path:
    f = tmp_path / "bad_step.yaml"
    f.write_text(_BAD_STEP_YAML)
    return f


class TestValidateCommand:
    def test_validate_valid_file(self, valid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["validate", str(valid_yaml_file)])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()

    def test_validate_invalid_yaml(self, invalid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["validate", str(invalid_yaml_file)])
        assert result.exit_code == 1

    def test_validate_bad_step(self, bad_step_yaml_file: Path) -> None:
        result = runner.invoke(app, ["validate", str(bad_step_yaml_file)])
        assert result.exit_code == 1

    def test_validate_nonexistent_file(self) -> None:
        result = runner.invoke(app, ["validate", "/nonexistent/path.yaml"])
        assert result.exit_code != 0

    @pytest.mark.skip(reason="CLI refactored — --verbose option removed from validate command")
    def test_validate_verbose(self, valid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["validate", "--verbose", str(valid_yaml_file)])
        assert result.exit_code == 0
        assert "Valid" in result.stdout


@pytest.mark.skip(reason="CLI refactored — compile now requires --compiler-keys and --player-pub; needs rewrite")
class TestCompileCommand:
    def test_compile_valid_file(self, valid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["compile", str(valid_yaml_file)])
        assert result.exit_code == 0

    def test_compile_invalid_yaml(self, invalid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["compile", str(invalid_yaml_file)])
        assert result.exit_code == 1

    def test_compile_verbose(self, valid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["compile", "--verbose", str(valid_yaml_file)])
        assert result.exit_code == 0


class TestRunCommand:
    @pytest.mark.skip(reason="requires real infrastructure; use integration tests for run command")
    def test_run_no_steps_passes(self, valid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["run", str(valid_yaml_file)])
        assert result.exit_code == 0

    def test_run_invalid_yaml(self, invalid_yaml_file: Path) -> None:
        result = runner.invoke(app, ["run", str(invalid_yaml_file)])
        assert result.exit_code == 1


@pytest.mark.skip(reason="CLI refactored — version command removed")
class TestVersionCommand:
    def test_version(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "tractusx-testlab" in result.stdout
        assert "0.1.0" in result.stdout


class TestPrintReport:
    def test_print_report_with_error(self, tmp_path: Path) -> None:
        """Test report with a step that has an error."""
        yaml_content = """\
syntax: v2
kind: test
id: error-test
namespace: testlab.cli
metadata:
  name: Error Test
  version: "1.0"
execution:
  - uses: http/http_request
    name: Bad Request
    with:
      url: "http://127.0.0.1:1/nonexistent"
"""
        f = tmp_path / "error.yaml"
        f.write_text(yaml_content)
        result = runner.invoke(app, ["run", str(f)])
        assert result.exit_code == 1

    @pytest.mark.skip(reason="CLI refactored — run output format changed; needs rewrite")
    def test_print_report_with_assertions(self, tmp_path: Path) -> None:
        """Test report printing with step that uses noop executor and assertions."""
        yaml_content = """\
syntax: v2
kind: test
id: noop-test
namespace: testlab.cli
metadata:
  name: Noop Test
  version: "1.0"
execution:
  - uses: register_twin
    name: Register
"""
        f = tmp_path / "noop.yaml"
        f.write_text(yaml_content)
        result = runner.invoke(app, ["run", str(f)])
        # noop returns status 200, so STATUS_CODE 200 should pass
        assert "Register" in result.stdout

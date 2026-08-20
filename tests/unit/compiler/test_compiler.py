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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Tests for the Compiler class (validate + compile pipeline)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.compiler.validation.validator import ValidationResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, content: dict, name: str = "script.yaml") -> Path:
    """Write a YAML dict to a temp file and return the path."""
    p = tmp_path / name
    p.write_text(yaml.dump(content, default_flow_style=False))
    return p


def _test_script(execution_steps: list | None = None) -> dict:
    """Return a minimal valid test script dict."""
    return {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "minimal-test",
        "namespace": "minimal-tck",
        "metadata": {
            "name": "Minimal Test",
            "version": "1.0",
            "description": "A minimal test script.",
        },
        "execution": execution_steps
        if execution_steps is not None
        else [{"id": "gen", "uses": "util/generate_uuid", "name": "gen"}],
    }


def _tck_manifest(test_filename: str = "minimal-test.yaml") -> dict:
    """Return a minimal valid TCK manifest dict referencing one test file."""
    return {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "minimal-tck",
        "metadata": {
            "name": "Minimal TCK",
            "version": "1.0",
            "description": "A minimal TCK manifest.",
            "standards": [{"id": "CX-0000", "version": "v1.0.0"}],
            "authors": [],
            "copyright_holders": [],
            "license": "Apache-2.0",
        },
        "env": {"variables": [], "schemas": []},
        "tests": [{"id": test_filename}],
    }


def _write_tck(tmp_path: Path, execution_steps: list | None = None) -> Path:
    """Write a TCK manifest + test file into tmp_path, return the manifest path."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write_yaml(tests_dir, _test_script(execution_steps), "minimal-test.yaml")
    return _write_yaml(tmp_path, _tck_manifest("minimal-test.yaml"), "tck.yaml")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompilerValidation:
    """Tests for Compiler.validate()."""

    def test_validate_minimal_valid_tck(self, tmp_path: Path) -> None:
        # Arrange
        script_path = _write_tck(tmp_path)
        compiler = Compiler()

        # Act
        result = compiler.validate(script_path)

        # Assert
        assert isinstance(result, ValidationResult)
        assert result.valid is True

    def test_validate_tck_with_steps(self, tmp_path: Path) -> None:
        # Arrange
        script_path = _write_tck(
            tmp_path, [{"id": "gen_id", "uses": "util/generate_uuid", "name": "gen"}]
        )
        compiler = Compiler()

        # Act
        result = compiler.validate(script_path)

        # Assert
        assert result.valid is True

    def test_validate_rejects_unknown_step_type(self, tmp_path: Path) -> None:
        # Arrange
        script_path = _write_tck(
            tmp_path, [{"id": "bad", "uses": "nonexistent_step_type_xyz", "name": "bad"}]
        )
        compiler = Compiler()

        # Act
        result = compiler.validate(script_path)

        # Assert
        assert result.valid is False
        assert any("nonexistent_step_type_xyz" in issue.message for issue in result.issues)

    def test_validate_returns_issues_for_multiple_bad_steps(self, tmp_path: Path) -> None:
        # Arrange
        script_path = _write_tck(
            tmp_path,
            [
                {"id": "a", "uses": "unknown_a", "name": "a"},
                {"id": "b", "uses": "unknown_b", "name": "b"},
            ],
        )
        compiler = Compiler()

        # Act
        result = compiler.validate(script_path)

        # Assert
        assert len(result.issues) >= 2

    def test_compile_raises_on_invalid_script(self, tmp_path: Path) -> None:
        # Arrange
        script_path = _write_tck(
            tmp_path, [{"id": "bogus", "uses": "totally_bogus_step", "name": "bogus"}]
        )
        compiler = Compiler()

        # Act & Assert
        with pytest.raises(ValueError, match="[Vv]alidation failed"):
            compiler.compile_plain(script_path, output_path=tmp_path / "out")

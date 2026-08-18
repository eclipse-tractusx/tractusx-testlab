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

"""Compiler — validates a TCK manifest and compiles it into a package."""

from __future__ import annotations

from pathlib import Path

import yaml

from tractusx_testlab.compiler.validation.validator import ScriptValidator, ValidationResult
from tractusx_testlab.scripting.parser import YamlParser


class Compiler:
    """High-level API: parse YAML → validate → compile.

    Sealing and encryption belong to the packaging step, not here — see
    :mod:`tractusx_testlab.cli.compile`.
    """

    __slots__ = ("_parser", "_validator")

    def __init__(self) -> None:
        self._validator = ScriptValidator()
        self._parser = YamlParser()

    def validate(self, script_path: Path, version: str | None = None) -> ValidationResult:
        """Validate a YAML tck and its tests without compiling."""
        from tractusx_testlab.compiler.validation._manifest_validation import validate_tck_manifest

        definition = self._parser.parse_tck(script_path)
        # Validate restrictions and rules of tck and test files
        result = self._validator.validate_tck(definition, script_path.parent, version=version)

        # Validate the tck and test files against JSON schemas
        try:
            manifest_data = yaml.safe_load(script_path.read_text(encoding="utf-8"))
            validate_tck_manifest(manifest_data, script_path.parent)
        except ValueError as exc:
            for line in str(exc).splitlines():
                if line.startswith("  - "):
                    result.add_error(line[4:])

        return result

    def compile_plain(
        self,
        manifest_path: Path,
        output_path: Path | None = None,
        version: str | None = None,
    ) -> tuple[dict, dict]:
        """Compile a TCK manifest into manifest.yaml + tck-execution.json.

        Args:
            manifest_path: Path to the TCK manifest YAML.
            output_path: Destination directory for output files.
            version: Optional compiler version string.

        Returns:
            Tuple of (manifest_dict, execution_dict).

        Raises:
            ValueError: If semantic validation produces errors.
        """
        from tractusx_testlab.compiler.ir.builder import build_ir

        validation_result = self.validate(manifest_path, version=version)
        if not validation_result.valid:
            raise ValueError(
                f"Validation failed with {len(validation_result.issues)} error(s):\n"
                + "\n".join(
                    f"  [{i.phase or 'step'}] {i.message}" for i in validation_result.issues
                )
            )

        if output_path is None:
            output_path = manifest_path.parent / "plain"

        return build_ir(
            manifest_path=manifest_path,
            output_path=output_path,
            version=version,
        )

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

"""Compiler — orchestrates validation + compilation into encrypted .stck packages."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from tractusx_testlab.compiler.packager import Packager
from tractusx_testlab.compiler.validation.validator import ScriptValidator, ValidationResult
from tractusx_testlab.models import PackageManifest
from tractusx_testlab.scripting.parser import YamlParser
from tractusx_testlab.security.trust.identity import PlayerIdentity


class Compiler:
    """High-level API: parse YAML → validate → encrypt + sign → .stck."""
    __slots__ = ("_validator", "_parser")

    def __init__(self) -> None:
        self._validator = ScriptValidator()
        self._parser = YamlParser()

    def validate(self, script_path: Path, version: Optional[str] = None) -> ValidationResult:
        """Validate a YAML tck and its tests without compiling."""
        from tractusx_testlab.compiler.validation._rules import validate_tck_manifest

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

    def compile(
        self,
        script_path: Path,
        compiler_identity: PlayerIdentity,
        recipient_keys: dict[str, bytes],
        output_path: Optional[Path] = None,
        version: Optional[str] = None,
    ) -> tuple[PackageManifest, ValidationResult]:
        """Validate and compile a script into a .tck archive.

        Args:
            script_path: Path to the YAML test script.
            compiler_identity: The compiler's identity (for signing).
            recipient_keys: {fingerprint: RSA public PEM} for each player.
            output_path: Destination file. Defaults to ``<script_name>.tck``.
            version: Optional connector version for version-specific validation.

        Returns:
            (manifest, validation_result) — manifest is None-free only if valid.

        Raises:
            ValueError: If validation produces errors.
        """
        definition = self._parser.parse_script(script_path)
        validation_result = self._validator.validate(definition, version=version)

        if not validation_result.valid:
            raise ValueError(
                f"Script validation failed with {sum(1 for issue in validation_result.issues if issue.level == 'error')} error(s): "
                + "; ".join(issue.message for issue in validation_result.issues if issue.level == "error")
            )

        script_yaml = script_path.read_bytes()
        if output_path is None:
            output_path = script_path.with_suffix(".stck")

        manifest = Packager.build(
            script_yaml=script_yaml,
            compiler_signing_key=compiler_identity.signing.private_bytes,
            compiler_id=compiler_identity.signing.fingerprint,
            recipient_public_keys=recipient_keys,
            output_path=output_path,
            name=definition.name,
            version=definition.version,
        )

        return manifest, validation_result

    def compile_plain(
        self,
        manifest_path: Path,
        output_path: Optional[Path] = None,
        version: Optional[str] = None,
    ) -> tuple[dict, dict]:
        """Compile a TCK manifest into manifest.yaml + tck-execution.json.

        Args:
            manifest_path: Path to the TCK manifest YAML.
            output_path: Destination directory for output files.
            version: Optional compiler version string.

        Returns:
            Tuple of (manifest_dict, execution_dict).
        """
        from tractusx_testlab.compiler.ir.builder import build_ir

        if output_path is None:
            output_path = manifest_path.parent / "plain"

        return build_ir(
            manifest_path=manifest_path,
            output_path=output_path,
            version=version,
        )

    def compile_tck(
        self,
        manifest_path: Path,
        compiler_identity: PlayerIdentity,
        recipient_keys: dict[str, bytes],
        output_path: Optional[Path] = None,
        version: Optional[str] = None,
    ) -> tuple[PackageManifest, ValidationResult]:
        """Compile a TCK manifest into a self-contained .tck.

        Referenced script files are inlined so the resulting package
        carries everything needed to run — no external files required.

        Args:
            manifest_path: Path to the TCK manifest YAML.
            compiler_identity: The compiler's identity (for signing).
            recipient_keys: {fingerprint: RSA public PEM} for each player.
            output_path: Destination .tck file.
            version: Optional connector version for validation.

        Returns:
            (manifest, validation_result)
        """
        with open(manifest_path, "r", encoding="utf-8") as manifest_file:
            tck_data = yaml.safe_load(manifest_file)

        inlined_tests, combined_validation = self._resolve_and_validate_test_entries(
            tck_data.get("tests", []),
            manifest_path.parent,
            version,
        )

        if not combined_validation.valid:
            errors = [issue for issue in combined_validation.issues if issue.level == "error"]
            raise ValueError(
                f"Validation failed with {len(errors)} error(s): "
                + "; ".join(issue.message for issue in errors)
            )

        tck_data["tests"] = inlined_tests
        bundled_yaml = yaml.dump(tck_data, default_flow_style=False, sort_keys=False).encode("utf-8")

        if output_path is None:
            output_path = manifest_path.with_suffix(".stck")

        name = tck_data.get("name", manifest_path.stem)
        ver = tck_data.get("version", "1.0")

        manifest = Packager.build(
            script_yaml=bundled_yaml,
            compiler_signing_key=compiler_identity.signing.private_bytes,
            compiler_id=compiler_identity.signing.fingerprint,
            recipient_public_keys=recipient_keys,
            output_path=output_path,
            name=name,
            version=ver,
        )

        return manifest, combined_validation

    def _resolve_and_validate_test_entries(
        self,
        tests_raw: list,
        base_dir: Path,
        version: Optional[str],
    ) -> tuple[list[dict], ValidationResult]:
        """Resolve string file references to inline dicts and validate each entry.

        Returns the list of inlined test dicts and a combined validation result.
        """
        inlined_tests: list[dict] = []
        combined_validation = ValidationResult()

        for entry in tests_raw:
            script_dict = self._load_test_entry(entry, base_dir)
            definition = YamlParser.parse_script_from_dict(script_dict)
            validation_result = self._validator.validate(definition, version=version)
            combined_validation.issues.extend(validation_result.issues)
            inlined_tests.append(script_dict)

        return inlined_tests, combined_validation

    @staticmethod
    def _load_test_entry(entry, base_dir: Path) -> dict:
        """Resolve a single test entry to a dict, loading from file if it's a string reference."""
        if isinstance(entry, dict):
            return entry

        # Strip the !include prefix if present
        _INCLUDE_PREFIX = "!include "
        if isinstance(entry, str) and entry.startswith(_INCLUDE_PREFIX):
            entry = entry[len(_INCLUDE_PREFIX):].strip()

        script_file = base_dir / entry
        if not script_file.exists():
            script_file = base_dir / "tests" / entry
        if not script_file.exists():
            raise FileNotFoundError(f"Referenced script not found: {entry}")

        with open(script_file, "r", encoding="utf-8") as script_handle:
            return yaml.safe_load(script_handle)

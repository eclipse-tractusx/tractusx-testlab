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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Loader — resolves YAML files, .tck archives, and .stck archives into Tck objects."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from tractusx_testlab.compiler.packager import Packager
from tractusx_testlab.scripting.script import Tck as Tck, TestScript
from tractusx_testlab.models.primitives.enums import ScriptKind
from tractusx_testlab.player.loading._parser import (
    _normalize_discriminator,
    _SCRIPT_ADAPTER,
    _TCK_ADAPTER,
    parse_script_file,
    parse_tck_file,
)

# Entry name for the bundled authoring YAML inside .tck ZIP archives
_TCK_BUNDLE_ENTRY = "tck-bundle.yaml"

logger = logging.getLogger(__name__)


def _load_test_scripts(tests: list, base_dir: Path) -> list[TestScript]:
    """Resolve TCK ``tests:`` entries into TestScript objects.

    Each entry is a ``TckTestEntry`` with an ``id`` filename relative to
    ``<base_dir>/tests/``.  The ``skippable`` flag from the manifest entry is
    forwarded to the ``TestScript`` so the player can enforce skip rules.
    """
    scripts: list[TestScript] = []
    tests_dir = base_dir / "tests"
    validation_errors = []
    for entry in tests:
        test_path = tests_dir / entry.id
        if not test_path.exists():
            logger.warning("Test file not found, skipping: %s", test_path)
            continue
        try:
            script_def = parse_script_file(test_path)
            scripts.append(TestScript(script_def, skippable=entry.skippable, test_id=entry.id))
        except ValidationError as e:
            # 3. if Pydantic fails, capture exception to add filename
            validation_errors.append(f"File: {entry.id}\n{e}")
    if validation_errors:
        separator = "\n" + "-" * 80 + "\n"
        raise ValueError(
            f"Can't run. Validation failure in {len(validation_errors)} test(s):"
            f"{separator}{separator.join(validation_errors)}"
        )
    return scripts

def _detect_kind(data: dict) -> ScriptKind:
    """Detect the kind of a YAML document.

    Priority: explicit ``kind`` field → structural heuristic (``tests`` key).
    Raises ``ValueError`` if ``kind`` contradicts the document structure.
    """
    explicit = data.get("kind")
    has_tests_key = "tests" in data

    if explicit is not None:
        kind = ScriptKind(explicit)
        if kind == ScriptKind.TEST and has_tests_key:
            raise ValueError(
                "YAML declares kind: test but contains a 'tests' key. "
                "Use kind: tck for manifests that group multiple tests."
            )
        if kind == ScriptKind.TCK and not has_tests_key:
            raise ValueError(
                "YAML declares kind: tck but is missing the 'tests' key. "
                "A TCK must list its tests under the 'tests' key."
            )
        return kind

    return ScriptKind.TCK if has_tests_key else ScriptKind.TEST


class Loader:
    """Loads a TCK from a YAML file, .tck archive, or .stck encrypted archive."""

    __slots__ = ()

    def load(
        self,
        path: Path,
        player_private_key: Optional[bytes] = None,
        compiler_public_key: Optional[bytes] = None,
    ) -> Tck:
        """Load a TCK from *path*.

        Uses the local parser to support testlab-extended enum values
        (assertion types, service types) that the SDK parser rejects.
        """
        if path.suffix == ".stck":
            return self._load_package(path, player_private_key, compiler_public_key)

        if path.suffix == ".tck":
            return self._load_tck_package(path)

        return self._load_yaml(path)

    def _load_tck_package(self, path: Path) -> Tck:
        """Load an unencrypted .tck ZIP archive.

        Extracts ``tck-bundle.yaml`` from the archive and parses it
        using the standard YAML pipeline.  The archive is extracted to
        a temporary directory so that relative asset paths resolve.
        """
        if not zipfile.is_zipfile(path):
            raise ValueError(
                f"File has .tck extension but is not a valid ZIP archive: {path}"
            )
        extract_dir = Path(tempfile.mkdtemp(prefix="tck_"))
        with zipfile.ZipFile(path, "r") as zf:
            if _TCK_BUNDLE_ENTRY not in zf.namelist():
                raise ValueError(
                    f"Package is missing the bundled test definition "
                    f"({_TCK_BUNDLE_ENTRY}). Re-compile the package with "
                    f"the latest testlab compiler."
                )
            zf.extractall(extract_dir)

        bundle_path = extract_dir / _TCK_BUNDLE_ENTRY
        with open(bundle_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return self._parse_data(data, source_path=path, base_dir=extract_dir)

    def _load_package(
        self,
        path: Path,
        player_private_key: Optional[bytes],
        compiler_public_key: Optional[bytes],
    ) -> Tck:
        """Load and verify a .stck archive."""
        if player_private_key is None or compiler_public_key is None:
            raise ValueError(
                "player_private_key and compiler_public_key are required "
                "to load .stck files"
            )
        yaml_bytes = Packager.extract_and_verify(
            path, player_private_key, compiler_public_key,
        )
        data = yaml.safe_load(yaml_bytes)
        return self._parse_data(data, source_path=path, base_dir=path.parent)

    def _load_yaml(self, path: Path) -> Tck:
        """Load a plain YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return self._parse_data(data, source_path=path, base_dir=path.parent)

    def _parse_data(self, data: object, source_path: Path, base_dir: Path) -> Tck:
        """Parse raw YAML data into a Tck runtime object.
        """
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected a YAML mapping from {source_path}, got {type(data).__name__}"
            )
        kind = _detect_kind(data)
        normalized = _normalize_discriminator(data, source_path)

        if kind == ScriptKind.TCK:
            tck_def = _TCK_ADAPTER.validate_python(normalized)
            tck = Tck(tck_def, base_dir=base_dir)
            tck._scripts = _load_test_scripts(tck_def.tests, base_dir)
            return tck
        else:
            script_def = _SCRIPT_ADAPTER.validate_python(normalized)
            return Tck.from_single_script(script_def, base_dir=base_dir)

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

"""Loader — resolves a ``.tck`` archive into a :class:`Tck`."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path

import yaml
from pydantic import ValidationError

from tractusx_testlab.authoring.test import Tck as Tck
from tractusx_testlab.authoring.test import Test
from tractusx_testlab.compiler import package_digest
from tractusx_testlab.models.authoring.definitions import TestDefinition
from tractusx_testlab.models.primitives.enums import DefinitionKind
from tractusx_testlab.player.loading._encrypted import PAYLOAD_ENTRY, open_encrypted_package
from tractusx_testlab.player.loading._parser import (
    _TCK_ADAPTER,
    _TEST_ADAPTER,
    _normalize_discriminator,
    parse_test_file,
)
from tractusx_testlab.syntax import diagnostics

# Entry name for the bundled authoring YAML inside .tck ZIP archives
_TCK_BUNDLE_ENTRY = "tck-bundle.yaml"

logger = logging.getLogger(__name__)


def _load_tests(entries: list, base_dir: Path) -> list[Test]:
    """Resolve TCK ``tests:`` entries into Test objects.

    Each entry is a ``TckTestEntry`` with an ``id`` filename relative to
    ``<base_dir>/tests/``.  The ``skippable`` flag from the manifest entry is
    forwarded to the ``Test`` so the player can enforce skip rules.
    """
    tests: list[Test] = []
    tests_dir = base_dir / "tests"
    validation_errors = []
    for entry in entries:
        test_path = tests_dir / entry.id
        if not test_path.exists():
            logger.warning("Test file not found, skipping: %s", test_path)
            continue
        try:
            test_def = parse_test_file(test_path)
            tests.append(Test(test_def, skippable=entry.skippable, test_id=entry.id))
        except ValidationError as exc:
            # 3. if Pydantic fails, capture exception to add filename
            findings = diagnostics.render(exc, model=TestDefinition, source=test_path)
            validation_errors.append(f"File: {entry.id}\n{findings}")
    if validation_errors:
        separator = "\n" + "-" * 80 + "\n"
        raise ValueError(
            f"Can't run. Validation failure in {len(validation_errors)} test(s):"
            f"{separator}{separator.join(validation_errors)}"
        )
    return tests


def _detect_kind(data: dict) -> DefinitionKind:
    """Detect the kind of a YAML document.

    Priority: explicit ``kind`` field → structural heuristic (``tests`` key).
    Raises ``ValueError`` if ``kind`` contradicts the document structure.
    """
    explicit = data.get("kind")
    has_tests_key = "tests" in data

    if explicit is not None:
        kind = DefinitionKind(explicit)
        if kind == DefinitionKind.TEST and has_tests_key:
            raise ValueError(
                "YAML declares kind: test but contains a 'tests' key. "
                "Use kind: tck for manifests that group multiple tests."
            )
        if kind == DefinitionKind.TCK and not has_tests_key:
            raise ValueError(
                "YAML declares kind: tck but is missing the 'tests' key. "
                "A TCK must list its tests under the 'tests' key."
            )
        return kind

    return DefinitionKind.TCK if has_tests_key else DefinitionKind.TEST


class Loader:
    """Loads a TCK from a ``.tck`` archive, plain or encrypted.

    A package and nothing else. The loader used to take authoring YAML too,
    and that branch was the one way into the player that skipped the compiler:
    no validator, no fingerprint, and no digest to check the executed files
    against. ``testlab run`` compiles a manifest and hands over the result.
    """

    __slots__ = ()

    def load(
        self,
        path: Path,
        player_private_key: bytes | None = None,
        compiler_public_key: bytes | None = None,
    ) -> Tck:
        """Load a TCK from the ``.tck`` package at *path*.

        Uses the local parser to support testlab-extended enum values
        (assertion types, service types) that the SDK parser rejects.

        Raises:
            ValueError: If *path* is not a ``.tck`` package.
        """
        if path.suffix != ".tck":
            raise ValueError(
                f"The player executes compiled packages, and {path.name!r} is not one. "
                f"Compile it first: `testlab compile {path} -o dist/`, then load the "
                f".tck this produces."
            )

        return self._load_tck_package(path, player_private_key, compiler_public_key)

    def _load_tck_package(
        self,
        path: Path,
        player_private_key: bytes | None = None,
        compiler_public_key: bytes | None = None,
    ) -> Tck:
        """Load a .tck ZIP archive — plain or encrypted (payload.enc format).

        Both shapes arrive at the same entries: read straight from a plain
        archive, or verified and decrypted from an encrypted one. Those are
        checked, extracted to a temporary directory so relative asset paths
        resolve, and ``tck-bundle.yaml`` is parsed.
        """
        if not zipfile.is_zipfile(path):
            raise ValueError(f"File has .tck extension but is not a valid ZIP archive: {path}")

        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()

        if PAYLOAD_ENTRY in names:
            entries = open_encrypted_package(path, player_private_key, compiler_public_key)
        else:
            with zipfile.ZipFile(path, "r") as zf:
                entries = {name: zf.read(name) for name in names}

        if _TCK_BUNDLE_ENTRY not in entries:
            raise ValueError(
                f"Package is missing the bundled test definition "
                f"({_TCK_BUNDLE_ENTRY}). Re-compile the package with "
                f"the latest testlab compiler."
            )

        # Verified before anything is written to disk, so a package that fails
        # never reaches a path something else might read.
        _verify_tck_integrity(entries)

        extract_dir = Path(tempfile.mkdtemp(prefix="tck_"))
        for name, blob in entries.items():
            target = extract_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)

        data = yaml.safe_load(entries[_TCK_BUNDLE_ENTRY].decode("utf-8"))
        return self._parse_data(data, source_path=path, base_dir=extract_dir)

    def _parse_data(self, data: object, source_path: Path, base_dir: Path) -> Tck:
        """Parse raw YAML data into a Tck runtime object."""
        if not isinstance(data, dict):
            raise ValueError(
                f"Expected a YAML mapping from {source_path}, got {type(data).__name__}"
            )
        kind = _detect_kind(data)
        normalized = _normalize_discriminator(data, source_path)

        if kind == DefinitionKind.TCK:
            tck_def = _TCK_ADAPTER.validate_python(normalized)
            tck = Tck(tck_def, base_dir=base_dir)
            tck._tests = _load_tests(tck_def.tests, base_dir)
            return tck
        else:
            test_def = _TEST_ADAPTER.validate_python(normalized)
            return Tck.from_single_test(test_def, base_dir=base_dir)


def _verify_tck_integrity(entries: dict[str, bytes]) -> None:
    """Refuse a package whose contents are not the ones it was sealed with.

    Delegates to :func:`~tractusx_testlab.compiler.package_digest.verify`, the
    same function the compiler seals with. The two used to be separate
    computations over two different sets of bytes: the digest covered
    ``manifest.yaml``, the compiled IR and the asset digests, while the player
    executed ``tests/*.yaml``, which was in none of them. A step appended to a
    test file inside a compiled ``.tck`` ran with no integrity error at all.
    """
    package_digest.verify(entries)

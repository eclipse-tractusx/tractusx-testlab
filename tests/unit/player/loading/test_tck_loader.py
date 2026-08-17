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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Regression tests for .tck plain ZIP archive loading via Loader."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tractusx_testlab.compiler import package_digest
from tractusx_testlab.player.loading.loader import _TCK_BUNDLE_ENTRY, Loader

_TCK_MANIFEST_YAML = """\
syntax: v1-alpha
kind: tck
id: tck-smoke
metadata:
  name: tck-smoke-test
  version: "1.0"
  description: A test bundled into a .tck archive
tests:
  - id: inline-test-one.yaml
    name: Inlined test one
"""

_TEST_SCRIPT_YAML = """\
syntax: v1-alpha
kind: test
id: inline-test-one
namespace: testlab.test
metadata:
  name: inline-test-one
  version: "1.0"
  description: Inlined test script
execution:
  - id: step_one
    uses: precondition/provide
    with:
      value: hello
    returns:
      greeting: {type: string}
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
    """Build a .tck ZIP archive with tck-bundle.yaml + tests/ and return the path."""
    archive_path = tmp_path / "bundle.tck"
    _write_sealed(archive_path, {
        _TCK_BUNDLE_ENTRY: _TCK_MANIFEST_YAML.encode(),
        "tests/inline-test-one.yaml": _TEST_SCRIPT_YAML.encode(),
    })
    return archive_path


class TestTckLoading:
    """Regression tests for .tck ZIP loading through Loader."""

    def test_load_tck_produces_valid_tck(self, tck_archive: Path) -> None:
        """A .tck ZIP archive loads correctly via the bundled YAML."""
        loader = Loader()

        tck = loader.load(tck_archive)

        assert tck.name == "tck-smoke-test"
        assert tck.script_count() == 1

    def test_load_tck_preserves_step_definitions(self, tck_archive: Path) -> None:
        """Steps declared in the bundled YAML survive the ZIP round-trip."""
        loader = Loader()

        tck = loader.load(tck_archive)
        script = tck.scripts[0]

        assert script.step_count() == 1
        assert script.steps[0].uses == "precondition/provide"

    def test_load_tck_rejects_non_zip_file(self, tmp_path: Path) -> None:
        """A non-ZIP file with .tck extension raises ValueError (not UnicodeDecodeError)."""
        fake_tck = tmp_path / "not-a-zip.tck"
        fake_tck.write_text("this is plain text, not a ZIP", encoding="utf-8")
        loader = Loader()

        with pytest.raises(ValueError, match="not a valid ZIP archive"):
            loader.load(fake_tck)

    def test_load_tck_rejects_zip_missing_bundle(self, tmp_path: Path) -> None:
        """A ZIP without tck-bundle.yaml raises ValueError with recompile hint."""
        archive_path = tmp_path / "no-bundle.tck"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("manifest.yaml", "kind: manifest\n")
        loader = Loader()

        with pytest.raises(ValueError, match="missing the bundled test definition"):
            loader.load(archive_path)

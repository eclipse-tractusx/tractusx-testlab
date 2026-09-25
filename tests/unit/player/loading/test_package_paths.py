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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A name inside a ``.tck`` package cannot reach outside it (GHSA-5982-hx9j-38f7).

The loader wrote every archive entry to ``extract_dir / name``: ``../x`` walked
out of the extraction directory and an absolute name replaced it, so a package
— which arrives through an unauthenticated upload, or from another
organisation — could create or overwrite any file the engine user can write,
before its bundle was even parsed. The same join read ``tests:`` ids and test
data sources, so a package could also read any file into a request it sends.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from tractusx_testlab.compiler import package_digest
from tractusx_testlab.player.execution._context_seeder import _resolve_asset_path
from tractusx_testlab.player.loading._package_paths import UnsafePackagePathError, package_path
from tractusx_testlab.player.loading.loader import _TCK_BUNDLE_ENTRY, Loader

_BUNDLE = b"""\
syntax: v1-alpha
kind: tck
id: tck-smoke
metadata:
  name: tck-smoke
  version: "1.0"
tests:
  - id: one.yaml
    name: One
"""

_TEST = b"""\
syntax: v1-alpha
kind: test
id: one
namespace: testlab.test
metadata:
  name: one
  version: "1.0"
execution:
  - id: step_one
    uses: precondition/provide
    with:
      value: hello
"""


def _package(path: Path, entries: dict[str, bytes]) -> Path:
    """A package sealed exactly as the compiler seals one — the digest is no defence."""
    sealed = package_digest.seal({"manifest.yaml": b"kind: manifest\n", **entries})
    with zipfile.ZipFile(path, "w") as zf:
        for name, blob in sealed.items():
            zf.writestr(name, blob)
    return path


class TestPackagePath:
    @pytest.mark.parametrize(
        "name",
        [
            "../escape.txt",
            "tests/../../escape.txt",
            "/etc/passwd",
            "C:/Windows/evil.dll",
            "C:evil",
            "..\\escape.txt",
            "tests\\..\\..\\escape.txt",
            "",
            "tests/\x00.yaml",
        ],
    )
    def test_a_name_that_leaves_the_package_is_refused(self, tmp_path: Path, name: str) -> None:
        with pytest.raises(UnsafePackagePathError):
            package_path(tmp_path, name)

    def test_a_name_inside_the_package_is_joined(self, tmp_path: Path) -> None:
        assert package_path(tmp_path, "tests/one.yaml") == tmp_path / "tests" / "one.yaml"

    def test_a_symbolic_link_out_of_the_package_is_refused(self, tmp_path: Path) -> None:
        base, outside = tmp_path / "pkg", tmp_path / "outside"
        base.mkdir()
        outside.mkdir()
        (base / "link").symlink_to(outside, target_is_directory=True)

        with pytest.raises(UnsafePackagePathError):
            package_path(base, "link/secret.json")


class TestLoadingAHostilePackage:
    @pytest.mark.parametrize("escape", ["../escape.txt", "absolute"])
    def test_nothing_is_written_outside(self, tmp_path: Path, escape: str) -> None:
        victim = tmp_path / "victim" / "escape.txt"
        name = str(victim) if escape == "absolute" else escape
        archive = _package(
            tmp_path / "hostile.tck",
            {_TCK_BUNDLE_ENTRY: _BUNDLE, "tests/one.yaml": _TEST, name: b"owned"},
        )

        with pytest.raises(UnsafePackagePathError):
            Loader().load(archive)

        assert not victim.exists()
        assert not (Path(__import__("tempfile").gettempdir()) / "escape.txt").exists()

    def test_a_refused_entry_stops_every_write(self, tmp_path: Path, monkeypatch) -> None:
        """Names are checked before the first byte lands — not entry by entry."""
        extract = tmp_path / "extract"
        extract.mkdir()
        monkeypatch.setattr("tempfile.mkdtemp", lambda prefix="": str(extract))
        archive = _package(
            tmp_path / "hostile.tck",
            {_TCK_BUNDLE_ENTRY: _BUNDLE, "tests/one.yaml": _TEST, "../escape.txt": b"x"},
        )

        with pytest.raises(UnsafePackagePathError):
            Loader().load(archive)

        assert list(extract.iterdir()) == []

    def test_a_tests_id_outside_the_package_is_refused(self, tmp_path: Path) -> None:
        # The manifest schema already refuses a separator in a tests id; the
        # loader's own check is the second line behind it.
        (tmp_path / "secret.yaml").write_bytes(_TEST)
        archive = _package(
            tmp_path / "hostile.tck",
            {
                _TCK_BUNDLE_ENTRY: _BUNDLE.replace(b"id: one.yaml", b"id: ../../secret.yaml"),
                "tests/one.yaml": _TEST,
            },
        )

        with pytest.raises(ValueError, match="secret.yaml"):
            Loader().load(archive)

    def test_a_well_formed_package_still_loads(self, tmp_path: Path) -> None:
        archive = _package(
            tmp_path / "ok.tck",
            {_TCK_BUNDLE_ENTRY: _BUNDLE, "tests/": b"", "tests/one.yaml": _TEST},
        )

        assert Loader().load(archive).name == "tck-smoke"


class TestAssetSources:
    def test_a_source_outside_the_package_is_refused(self, tmp_path: Path) -> None:
        base = tmp_path / "pkg"
        (base / "testdata").mkdir(parents=True)
        (tmp_path / "secret.json").write_text("{}")

        with pytest.raises(UnsafePackagePathError):
            _resolve_asset_path(base, "testdata", "../../secret.json")

    def test_a_source_inside_is_found(self, tmp_path: Path) -> None:
        (tmp_path / "assets" / "testdata").mkdir(parents=True)
        (tmp_path / "assets" / "testdata" / "body.json").write_text("{}")

        assert _resolve_asset_path(tmp_path, "testdata", "body.json") == (
            tmp_path / "assets" / "testdata" / "body.json"
        )

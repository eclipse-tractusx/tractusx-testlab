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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Package storage never reads, writes or removes anything outside its root.

The upload's file name gives a stored package its name and version, and a
``package_id`` arrives in a URL segment or a request body — both chosen by
whoever reaches the server, which a run exposes to the system under test.
A file name like ``../../../outside/evil-1.0.tck`` wrote the upload outside
the storage root, and ``DELETE /testlab/packages/..`` removed the whole
``storage_dir``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.server.app import create_app
from tractusx_testlab.server.routes import jobs as jobs_routes
from tractusx_testlab.server.storage import (
    InvalidPackageNameError,
    PackageStorage,
    is_package_id,
    new_package_id,
)

_BODY = b"ATTACKER PACKAGE BYTES"


@pytest.fixture()
def storage_dir(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture()
def client(tmp_path: Path, storage_dir: Path) -> TestClient:
    (tmp_path / "logs").mkdir()
    config = TestlabConfig(storage_dir=storage_dir, logs_dir=tmp_path / "logs")
    return TestClient(create_app(config), raise_server_exceptions=False)


def _files_outside(root: Path, tmp_path: Path) -> list[Path]:
    return [p for p in tmp_path.rglob("*.tck") if not p.is_relative_to(root)]


class TestUpload:
    def test_a_bare_file_name_is_stored_in_its_package(
        self, client: TestClient, storage_dir: Path
    ) -> None:
        response = client.post(
            "/testlab/packages",
            files={"file": ("my-tck-1.0.tck", _BODY, "application/octet-stream")},
        )

        assert response.status_code == 201
        body = response.json()
        assert is_package_id(body["package_id"])
        stored = Path(body["file_path"])
        assert stored == storage_dir / "packages" / body["package_id"] / "my-tck-1.0.tck"
        assert stored.read_bytes() == _BODY

    @pytest.mark.parametrize(
        "filename",
        [
            "../../../outside/evil-1.0.tck",
            "../evil-1.0.tck",
            "sub/evil-1.0.tck",
            "..\\..\\outside\\evil-1.0.tck",
            "evil-../../outside.tck",
            "..-1.0.tck",
            "/abs/evil-1.0.tck",
        ],
    )
    def test_a_file_name_with_a_path_is_refused(
        self, client: TestClient, storage_dir: Path, tmp_path: Path, filename: str
    ) -> None:
        (tmp_path / "outside").mkdir()

        response = client.post(
            "/testlab/packages", files={"file": (filename, _BODY, "application/octet-stream")}
        )

        assert response.status_code == 400
        assert _files_outside(storage_dir / "packages", tmp_path) == []
        assert list((storage_dir / "packages").iterdir()) == []


class TestDelete:
    @pytest.mark.parametrize("package_id", ["%2E%2E", "%2E"])
    def test_a_dot_segment_removes_nothing(
        self, client: TestClient, storage_dir: Path, package_id: str
    ) -> None:
        marker = storage_dir / "operator_data.txt"
        marker.write_text("keep")
        kept = client.post(
            "/testlab/packages", files={"file": ("kept-1.0.tck", _BODY, "application/octet-stream")}
        ).json()

        response = client.delete(f"/testlab/packages/{package_id}")

        assert response.status_code == 404
        assert marker.read_text() == "keep"
        assert Path(kept["file_path"]).read_bytes() == _BODY

    def test_an_uploaded_package_is_removed(self, client: TestClient) -> None:
        uploaded = client.post(
            "/testlab/packages", files={"file": ("gone-1.0.tck", _BODY, "application/octet-stream")}
        ).json()

        assert client.delete(f"/testlab/packages/{uploaded['package_id']}").status_code == 204
        assert not Path(uploaded["file_path"]).exists()
        assert client.delete(f"/testlab/packages/{uploaded['package_id']}").status_code == 404


class TestRun:
    def test_a_dot_segment_package_id_names_no_package(self, client: TestClient) -> None:
        response = client.post("/testlab/run/package", json={"package_id": ".."})

        assert response.status_code == 404


class TestRunByPath:
    """A ``path`` names a package in the store — never any other file on the server."""

    @pytest.fixture()
    def started(self, monkeypatch: pytest.MonkeyPatch) -> list[Path]:
        """What the server set out to run; nothing actually runs."""
        targets: list[Path] = []

        async def record(_player: object, target: Path, _runtime_vars: dict) -> None:
            targets.append(target)

        monkeypatch.setattr(jobs_routes, "_execute_in_background", record)
        return targets

    @pytest.fixture()
    def outside(self, tmp_path: Path) -> Path:
        package = tmp_path / "elsewhere" / "planted-1.0.tck"
        package.parent.mkdir()
        package.write_bytes(_BODY)
        return package

    def _run(self, client: TestClient, path: Path | str) -> Any:
        return client.post("/testlab/run/package", json={"path": str(path)})

    def test_a_package_outside_the_store_is_refused(
        self, client: TestClient, outside: Path, started: list[Path]
    ) -> None:
        response = self._run(client, outside)

        assert response.status_code == 403
        assert started == []
        assert client.get("/testlab/tck-execution").json() == []

    def test_a_path_that_climbs_out_of_the_store_is_refused(
        self, client: TestClient, storage_dir: Path, outside: Path, started: list[Path]
    ) -> None:
        climbing = storage_dir / "packages" / ".." / ".." / "elsewhere" / outside.name

        assert self._run(client, climbing).status_code == 403
        assert started == []

    def test_a_link_in_the_store_to_a_file_outside_is_refused(
        self, client: TestClient, storage_dir: Path, outside: Path, started: list[Path]
    ) -> None:
        link = storage_dir / "packages" / "linked-1.0.tck"
        link.symlink_to(outside)

        assert self._run(client, link).status_code == 403
        assert started == []

    def test_a_missing_file_outside_the_store_is_refused_the_same(
        self, client: TestClient, tmp_path: Path, started: list[Path]
    ) -> None:
        """403 whether it exists or not: the answer says nothing about the disk."""
        assert self._run(client, tmp_path / "nowhere-1.0.tck").status_code == 403
        assert started == []

    def test_a_package_in_the_store_runs(self, client: TestClient, started: list[Path]) -> None:
        uploaded = client.post(
            "/testlab/packages", files={"file": ("mine-1.0.tck", _BODY, "application/octet-stream")}
        ).json()

        response = self._run(client, uploaded["file_path"])

        assert response.status_code == 202
        assert started == [Path(uploaded["file_path"])]


class TestPackageStorage:
    def test_ids_it_issues_are_package_ids(self) -> None:
        assert is_package_id(new_package_id())

    @pytest.mark.parametrize(
        "package_id", ["..", ".", "", "ABCDEF123456", "0123456789ab/..", "0123456789abc"]
    )
    def test_anything_else_names_no_package(self, tmp_path: Path, package_id: str) -> None:
        storage = PackageStorage(tmp_path / "packages")

        assert storage.get(package_id) is None
        assert storage.get_path(package_id) is None
        assert storage.delete(package_id) is False
        assert tmp_path.joinpath("packages").is_dir()

    @pytest.mark.parametrize(
        ("name", "version"),
        [("../x", "1.0"), ("x", "../1.0"), ("..", "1.0"), ("x", "a/b"), ("x\x00", "1")],
    )
    def test_save_refuses_a_path_in_name_or_version(
        self, tmp_path: Path, name: str, version: str
    ) -> None:
        storage = PackageStorage(tmp_path / "packages")

        with pytest.raises(InvalidPackageNameError):
            storage.save(new_package_id(), name, version, _BODY)
        assert list(tmp_path.rglob("*.tck")) == []

    def test_save_refuses_an_id_it_did_not_issue(self, tmp_path: Path) -> None:
        storage = PackageStorage(tmp_path / "packages")

        with pytest.raises(InvalidPackageNameError):
            storage.save("..", "x", "1.0", _BODY)

    def test_delete_does_not_follow_a_symlink_out_of_the_root(self, tmp_path: Path) -> None:
        storage = PackageStorage(tmp_path / "packages")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "keep.tck").write_bytes(_BODY)
        link = tmp_path / "packages" / "0123456789ab"
        link.symlink_to(elsewhere, target_is_directory=True)

        assert storage.delete("0123456789ab") is False
        assert (elsewhere / "keep.tck").read_bytes() == _BODY

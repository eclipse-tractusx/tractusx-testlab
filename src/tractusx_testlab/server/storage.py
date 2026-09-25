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

"""Package storage — filesystem-backed storage for uploaded .tck archives."""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from tractusx_testlab.models import PackageFormat, UploadedPackage

#: The form of a ``package_id`` this storage hands out (``new_package_id``).
#: Anything else names no package: an id reaches the storage from a URL segment
#: or a request body, so ``..`` or ``.`` would otherwise address the storage
#: root or its parent.
PACKAGE_ID_PATTERN = re.compile(r"[0-9a-f]{12}")


class InvalidPackageNameError(ValueError):
    """The name or version of an upload is not a single file-name segment."""


def new_package_id() -> str:
    """A fresh ``package_id``: twelve lowercase hex digits."""
    return uuid.uuid4().hex[:12]


def is_package_id(value: str) -> bool:
    """Whether *value* has the form of a ``package_id`` this storage issues."""
    return PACKAGE_ID_PATTERN.fullmatch(value) is not None


def _is_segment(value: str) -> bool:
    """Whether *value* is one file-name segment: no separator, no dot segment."""
    return bool(value) and value not in {".", ".."} and not any(c in value for c in "/\\\x00")


class PackageStorage:
    """Stores and retrieves uploaded TCK packages on the local filesystem."""

    __slots__ = ("_base_dir",)

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _package_dir(self, package_id: str) -> Path | None:
        """The directory of *package_id*, or ``None`` when it is not a package id."""
        if not is_package_id(package_id):
            return None
        return self._base_dir / package_id

    def _contains(self, path: Path) -> bool:
        """Whether *path* resolves to a location strictly inside the storage root."""
        root = self._base_dir.resolve()
        resolved = path.resolve()
        return resolved != root and resolved.is_relative_to(root)

    def save(self, package_id: str, name: str, version: str, data: bytes) -> UploadedPackage:
        """Persist package bytes and return metadata.

        Raises:
            InvalidPackageNameError: *name* or *version* is not a single file-name
                segment, or *package_id* is not one this storage issues — the
                file would land outside the package's own directory.
        """
        pkg_dir = self._package_dir(package_id)
        if pkg_dir is None:
            raise InvalidPackageNameError(f"Invalid package id: {package_id!r}")
        if not (_is_segment(name) and _is_segment(version)):
            raise InvalidPackageNameError(
                f"Package name and version must not contain a path: {name!r}, {version!r}"
            )
        file_path = pkg_dir / f"{name}-{version}.tck"
        if file_path.resolve().parent != pkg_dir.resolve():
            raise InvalidPackageNameError(f"Package file escapes its directory: {file_path.name!r}")
        pkg_dir.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)

        return UploadedPackage(
            package_id=package_id,
            name=name,
            version=version,
            format=PackageFormat.ENCRYPTED,
            size_bytes=len(data),
            uploaded_at=datetime.now(UTC),
            checksum=hashlib.sha256(data).hexdigest(),
            file_path=str(file_path),
        )

    def get(self, package_id: str) -> UploadedPackage | None:
        """Load metadata for a stored package."""
        pkg_dir = self._package_dir(package_id)
        if pkg_dir is None or not pkg_dir.is_dir():
            return None

        files = list(pkg_dir.glob("*.tck"))
        if not files:
            return None

        file_path = files[0]
        data = file_path.read_bytes()
        stem = file_path.stem  # "name-version"

        return UploadedPackage(
            package_id=package_id,
            name=stem,
            version="",
            format=PackageFormat.ENCRYPTED,
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
            file_path=str(file_path),
        )

    def get_path(self, package_id: str) -> Path | None:
        """Return the filesystem path for a stored package."""
        pkg_dir = self._package_dir(package_id)
        if pkg_dir is None or not pkg_dir.is_dir():
            return None
        files = list(pkg_dir.glob("*.tck"))
        return files[0] if files else None

    def delete(self, package_id: str) -> bool:
        """Remove a package from storage. Returns True if it existed.

        Only a directory named like an issued ``package_id`` and lying inside the
        storage root is removed: ``..``, ``.`` or a symlink out of the root
        name no package.
        """
        pkg_dir = self._package_dir(package_id)
        if pkg_dir is None or pkg_dir.is_symlink() or not self._contains(pkg_dir):
            return False
        if pkg_dir.is_dir():
            shutil.rmtree(pkg_dir)
            return True
        return False

    def list_packages(self) -> list[UploadedPackage]:
        """List all stored packages."""
        result: list[UploadedPackage] = []
        if not self._base_dir.is_dir():
            return result

        for pkg_dir in sorted(self._base_dir.iterdir()):
            if not pkg_dir.is_dir():
                continue
            pkg = self.get(pkg_dir.name)
            if pkg:
                result.append(pkg)
        return result

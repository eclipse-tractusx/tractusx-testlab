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

"""Package storage — filesystem-backed storage for uploaded .stck archives."""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

from tractusx_testlab.models import PackageFormat, UploadedPackage


class PackageStorage:
    """Stores and retrieves uploaded test packages on the local filesystem."""

    __slots__ = ("_base_dir",)

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, package_id: str, name: str, version: str, data: bytes) -> UploadedPackage:
        """Persist package bytes and return metadata."""
        pkg_dir = self._base_dir / package_id
        pkg_dir.mkdir(parents=True, exist_ok=True)
        file_path = pkg_dir / f"{name}-{version}.stck"
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
        pkg_dir = self._base_dir / package_id
        if not pkg_dir.is_dir():
            return None

        files = list(pkg_dir.glob("*.stck"))
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
        pkg_dir = self._base_dir / package_id
        if not pkg_dir.is_dir():
            return None
        files = list(pkg_dir.glob("*.stck"))
        return files[0] if files else None

    def delete(self, package_id: str) -> bool:
        """Remove a package from storage. Returns True if it existed."""
        pkg_dir = self._base_dir / package_id
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

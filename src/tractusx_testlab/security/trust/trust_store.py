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

"""Trust store — manages trusted compiler public keys for signature verification."""

from __future__ import annotations

import hashlib
from pathlib import Path


class TrustStore:
    """A directory-backed store of trusted Ed25519 compiler public keys."""

    __slots__ = ("_dir",)

    def __init__(self, directory: Path) -> None:
        self._dir = directory
        self._dir.mkdir(parents=True, exist_ok=True)

    def add(self, public_pem: bytes, label: str | None = None) -> str:
        """Add a public key and return its fingerprint."""
        fingerprint = hashlib.sha256(public_pem).hexdigest()
        name = label or fingerprint[:16]
        (self._dir / f"{name}.pub").write_bytes(public_pem)
        return fingerprint

    def remove(self, label: str) -> bool:
        """Remove a key by label. Returns True if found."""
        path = self._dir / f"{label}.pub"
        if path.exists():
            path.unlink()
            return True
        return False

    def get(self, label: str) -> bytes | None:
        """Retrieve a public key by label."""
        path = self._dir / f"{label}.pub"
        return path.read_bytes() if path.exists() else None

    def list_keys(self) -> list[str]:
        """Return labels of all stored keys."""
        return [p.stem for p in sorted(self._dir.glob("*.pub"))]

    def is_trusted(self, public_pem: bytes) -> bool:
        """Check whether a public key is in the store (by content comparison)."""
        return any(path.read_bytes() == public_pem for path in self._dir.glob("*.pub"))

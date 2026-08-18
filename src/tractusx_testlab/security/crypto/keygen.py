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

"""RSA and Ed25519 key pair generation for package encryption and signing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa


@dataclass(frozen=True, slots=True)
class KeyPair:
    """An asymmetric key pair with its fingerprint."""

    private_bytes: bytes
    public_bytes: bytes
    fingerprint: str  # SHA-256 hex of public key DER


def _fingerprint(public_bytes: bytes) -> str:
    """SHA-256 fingerprint of raw public key bytes."""
    return hashlib.sha256(public_bytes).hexdigest()


def generate_rsa_keypair(key_size: int = 4096) -> KeyPair:
    """Generate an RSA key pair (for AES key wrapping)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair(
        private_bytes=private_bytes,
        public_bytes=public_bytes,
        fingerprint=_fingerprint(public_bytes),
    )


def generate_ed25519_keypair() -> KeyPair:
    """Generate an Ed25519 key pair (for package signing)."""
    private_key = ed25519.Ed25519PrivateKey.generate()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return KeyPair(
        private_bytes=private_bytes,
        public_bytes=public_bytes,
        fingerprint=_fingerprint(public_bytes),
    )


def save_keypair(kp: KeyPair, directory: Path, name: str) -> None:
    """Persist a key pair as PEM files."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.pem").write_bytes(kp.private_bytes)
    (directory / f"{name}.pub").write_bytes(kp.public_bytes)


def load_public_key(path: Path) -> bytes:
    """Load a PEM-encoded public key from disk."""
    return path.read_bytes()


def load_private_key(path: Path) -> bytes:
    """Load a PEM-encoded private key from disk."""
    return path.read_bytes()

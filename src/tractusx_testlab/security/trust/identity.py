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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Player identity — RSA and ML-KEM-768 key pairs for encryption, Ed25519 for signing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TypedDict

from tractusx_testlab.security.crypto.keygen import (
    KeyPair,
    _fingerprint,
    generate_ed25519_keypair,
    generate_mlkem_keypair,
    generate_rsa_keypair,
    load_private_key,
    load_public_key,
    save_keypair,
)

#: File stem of each key pair in an identity directory (``<stem>.pem`` / ``<stem>.pub``).
ENCRYPTION_KEY = "encryption"
PQ_ENCRYPTION_KEY = f"{ENCRYPTION_KEY}_pq"
SIGNING_KEY = "signing"


@dataclass(frozen=True, slots=True)
class PlayerIdentity:
    """A player's cryptographic identity for encrypting and signing packages.

    ``pq_encryption`` is optional: an identity made before the hybrid key wrap
    (ADR-0012) has none, and packages are sealed for it with RSA-OAEP alone.
    """

    encryption: KeyPair  # RSA — for AES key wrapping
    signing: KeyPair  # Ed25519 — for package signing
    pq_encryption: KeyPair | None = None  # ML-KEM-768 — the post-quantum half of the wrap

    @staticmethod
    def generate() -> PlayerIdentity:
        """Create a fresh identity with new RSA, ML-KEM-768 and Ed25519 key pairs."""
        return PlayerIdentity(
            encryption=generate_rsa_keypair(),
            signing=generate_ed25519_keypair(),
            pq_encryption=generate_mlkem_keypair(),
        )

    def with_pq_encryption(self) -> PlayerIdentity:
        """This identity, given an ML-KEM-768 pair if it has none yet."""
        if self.pq_encryption is not None:
            return self
        return replace(self, pq_encryption=generate_mlkem_keypair())

    def save(self, directory: Path) -> None:
        """Persist every key pair into *directory*."""
        save_keypair(self.encryption, directory, ENCRYPTION_KEY)
        save_keypair(self.signing, directory, SIGNING_KEY)
        if self.pq_encryption is not None:
            save_keypair(self.pq_encryption, directory, PQ_ENCRYPTION_KEY)

    @staticmethod
    def load(directory: Path) -> PlayerIdentity:
        """Load a persisted identity from *directory*; the ML-KEM pair only if it is there."""
        return PlayerIdentity(
            encryption=_load_pair(directory, ENCRYPTION_KEY),
            signing=_load_pair(directory, SIGNING_KEY),
            pq_encryption=(
                _load_pair(directory, PQ_ENCRYPTION_KEY)
                if (directory / f"{PQ_ENCRYPTION_KEY}.pem").is_file()
                else None
            ),
        )


def _load_pair(directory: Path, stem: str) -> KeyPair:
    public = load_public_key(directory / f"{stem}.pub")
    return KeyPair(load_private_key(directory / f"{stem}.pem"), public, _fingerprint(public))


def pq_public_key_beside(encryption_pub: Path) -> bytes | None:
    """The ML-KEM-768 key that travels with a player's RSA public key, if any.

    ``<name>.pub`` pairs with ``<name>_pq.pub`` in the same directory —
    ``encryption.pub`` with ``encryption_pq.pub`` as ``testlab keygen`` writes
    them, ``acme.pub`` with ``acme_pq.pub`` once renamed for a compiler's
    collection. Finding it there seals for the player with the hybrid wrap
    without a second flag to forget.
    """
    candidate = encryption_pub.with_name(f"{encryption_pub.stem}_pq.pub")
    return candidate.read_bytes() if candidate.is_file() else None


class PlayerKeys(TypedDict, total=False):
    """A player's private keys, under the names ``Loader.load`` takes them by."""

    player_private_key: bytes
    player_kem_private_key: bytes


def decryption_keys(directory: Path) -> PlayerKeys:
    """The player's private keys in *directory*: RSA, and ML-KEM-768 when it has one."""
    keys = PlayerKeys(player_private_key=load_private_key(directory / f"{ENCRYPTION_KEY}.pem"))
    pq_private = directory / f"{PQ_ENCRYPTION_KEY}.pem"
    if pq_private.is_file():
        keys["player_kem_private_key"] = load_private_key(pq_private)
    return keys

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

"""Player identity — RSA key pair for encryption, Ed25519 key pair for signing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tractusx_testlab.security.crypto.keygen import (
    KeyPair,
    generate_ed25519_keypair,
    generate_rsa_keypair,
    load_private_key,
    load_public_key,
    save_keypair,
)


@dataclass(frozen=True, slots=True)
class PlayerIdentity:
    """A player's cryptographic identity for encrypting and signing packages."""
    encryption: KeyPair   # RSA — for AES key wrapping
    signing: KeyPair      # Ed25519 — for package signing

    @staticmethod
    def generate() -> PlayerIdentity:
        """Create a fresh identity with new RSA and Ed25519 key pairs."""
        return PlayerIdentity(
            encryption=generate_rsa_keypair(),
            signing=generate_ed25519_keypair(),
        )

    def save(self, directory: Path) -> None:
        """Persist both key pairs into *directory*."""
        save_keypair(self.encryption, directory, "encryption")
        save_keypair(self.signing, directory, "signing")

    @staticmethod
    def load(directory: Path) -> PlayerIdentity:
        """Load a persisted identity from *directory*."""
        enc_priv = load_private_key(directory / "encryption.pem")
        enc_pub = load_public_key(directory / "encryption.pub")
        sign_priv = load_private_key(directory / "signing.pem")
        sign_pub = load_public_key(directory / "signing.pub")

        from tractusx_testlab.security.crypto.keygen import _fingerprint

        return PlayerIdentity(
            encryption=KeyPair(enc_priv, enc_pub, _fingerprint(enc_pub)),
            signing=KeyPair(sign_priv, sign_pub, _fingerprint(sign_pub)),
        )

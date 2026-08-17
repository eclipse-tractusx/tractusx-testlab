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

"""Package builder/reader — creates encrypted, signed .stck ZIP archives."""

from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from tractusx_testlab.models import (
    EncryptedKeyBlock,
    PackageManifest,
    SecurityBlock,
)
from tractusx_testlab.security.crypto.encryption import decrypt_package, encrypt_package
from tractusx_testlab.security.crypto.signing import sign_bytes, verify_signature

# Archive entry names
_MANIFEST = "manifest.json"
_PAYLOAD = "tck.bin"
_SIGNATURE = "signature.bin"


class Packager:
    """Create and read encrypted, signed .stck archives."""

    @staticmethod
    def build(
        script_yaml: bytes,
        compiler_signing_key: bytes,
        compiler_id: str,
        recipient_public_keys: dict[str, bytes],
        output_path: Path,
        name: str = "",
        version: str = "1.0",
    ) -> PackageManifest:
        """Build a .stck file.

        Args:
            script_yaml: Raw YAML content to package.
            compiler_signing_key: Ed25519 private key PEM for signing.
            compiler_id: Fingerprint/ID of the compiler's signing key.
            recipient_public_keys: {player_id: RSA public PEM} for each recipient.
            output_path: Destination .stck file.
            name: Package name.
            version: Package version.

        Returns:
            The PackageManifest written into the archive.
        """
        checksum = hashlib.sha256(script_yaml).hexdigest()
        signature = sign_bytes(script_yaml, compiler_signing_key)

        authorized_players: list[EncryptedKeyBlock] = []

        for player_id, pub_pem in recipient_public_keys.items():
            enc_key, nonce_data, ciphertext = encrypt_package(script_yaml, pub_pem)
            authorized_players.append(EncryptedKeyBlock(
                player_id=player_id,
                encrypted_key=enc_key,
            ))

        # We store the last nonce+ciphertext (all recipients encrypt the same plaintext)
        security = SecurityBlock(
            format="stck",
            algorithm="AES-256-GCM",
            key_derivation="RSA-OAEP-SHA256",
            compiler_id=compiler_id,
            authorized_players=authorized_players,
        )

        manifest = PackageManifest(
            name=name,
            version=version,
            compiled_at=datetime.now(UTC),
            checksum=checksum,
            security=security,
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(_MANIFEST, manifest.model_dump_json(indent=2))
            zf.writestr(_PAYLOAD, base64.b64encode(nonce_data + ciphertext).decode())
            zf.writestr(_SIGNATURE, base64.b64encode(signature).decode())

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(buf.getvalue())
        return manifest

    @staticmethod
    def read_manifest(package_path: Path) -> PackageManifest:
        """Extract and parse the manifest from a .stck file."""
        with zipfile.ZipFile(package_path, "r") as zf:
            raw = zf.read(_MANIFEST)
        return PackageManifest.model_validate_json(raw)

    @staticmethod
    def extract_and_verify(
        package_path: Path,
        player_private_key: bytes,
        compiler_public_key: bytes,
    ) -> bytes:
        """Decrypt and verify a .stck archive.

        Returns:
            The decrypted script YAML bytes.

        Raises:
            ValueError: If signature verification fails.
        """
        with zipfile.ZipFile(package_path, "r") as zf:
            manifest_raw = zf.read(_MANIFEST)
            script_blob = base64.b64decode(zf.read(_PAYLOAD))
            signature = base64.b64decode(zf.read(_SIGNATURE))

        manifest = PackageManifest.model_validate_json(manifest_raw)
        nonce = script_blob[:12]
        ciphertext = script_blob[12:]

        # Find the encrypted key for our player (use first available)
        encrypted_key = manifest.security.authorized_players[0].encrypted_key

        plaintext = decrypt_package(encrypted_key, nonce, ciphertext, player_private_key)

        # Verify signature
        if not verify_signature(plaintext, signature, compiler_public_key):
            raise ValueError("Package signature verification failed — untrusted source")

        # Verify content hash
        if hashlib.sha256(plaintext).hexdigest() != manifest.checksum:
            raise ValueError("Content hash mismatch — package may be corrupted")

        return plaintext

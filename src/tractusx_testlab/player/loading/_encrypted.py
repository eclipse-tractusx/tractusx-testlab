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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Opening an encrypted ``.tck`` — verify what is readable, then decrypt the rest.

An encrypted package keeps its ``manifest.yaml`` in the clear so anyone can read
what it is. The Compiler's signature covers that manifest together with
``payload.enc``, so the readable part is as tamper-evident as the encrypted part,
and it is checked before a single byte is decrypted.
"""

from __future__ import annotations

import base64
import io
import tarfile
import zipfile
from pathlib import Path

import yaml

from tractusx_testlab.compiler import package_digest
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.loading._parser import encrypted_package_compiler_id
from tractusx_testlab.security.crypto.encryption import content_key_for, decrypt_payload
from tractusx_testlab.security.crypto.signing import package_signing_message, verify_signature
from tractusx_testlab.security.trust.identity import ENCRYPTION_KEY, PlayerKeys, decryption_keys
from tractusx_testlab.security.trust.trust_store import TrustStore

#: Archive entries of an encrypted package.
MANIFEST_ENTRY = "manifest.yaml"
PAYLOAD_ENTRY = "payload.enc"
SIGNATURE_ENTRY = "signature.sig"


class PackageKeys(PlayerKeys, total=False):
    """The keys ``Loader.load`` opens an encrypted package with: the player's and the compiler's."""

    compiler_public_key: bytes


def verify_manifest(path: Path, compiler_public_key: bytes | None) -> dict:
    """Return the readable manifest of the encrypted package at *path*, verified.

    Needs only the Compiler's public key, not a Player's: anyone the Compiler
    shared ``signing.pub`` with can confirm the manifest they are reading is the
    one it signed.

    The signature is over :func:`package_signing_message` of the exact
    ``manifest.yaml`` and ``payload.enc`` bytes in the archive. It used to cover
    only the decrypted TAR, so the manifest — ``tck`` identity, checksum,
    ``compiler_id``, the list of authorized players — could be edited freely.
    """
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        manifest_raw = archive.read(MANIFEST_ENTRY)
        payload_raw = archive.read(PAYLOAD_ENTRY)
        signature_raw = archive.read(SIGNATURE_ENTRY) if SIGNATURE_ENTRY in names else None

    # A signed package is verified or refused; there is no third outcome. This
    # used to be `if compiler_public_key and sig_raw:`, so a caller that supplied
    # no key simply skipped the check.
    if signature_raw is None:
        raise ValueError(
            f"Encrypted package {path.name!r} carries no signature. It cannot "
            f"be shown to come from the compiler it claims."
        )
    if compiler_public_key is None:
        raise ValueError(
            f"Encrypted package {path.name!r} is signed, but no compiler public "
            f"key was supplied to check it against. Pass --compiler-pub."
        )
    message = package_signing_message(manifest_raw, payload_raw)
    if not verify_signature(message, base64.b64decode(signature_raw), compiler_public_key):
        raise ValueError(
            "Package signature verification failed — untrusted source. The manifest "
            "or the payload is not the one the compiler signed."
        )
    return yaml.safe_load(manifest_raw) or {}


def open_encrypted_package(
    path: Path,
    player_private_key: bytes | None,
    compiler_public_key: bytes | None,
    player_kem_private_key: bytes | None = None,
    *,
    require_hybrid: bool = False,
) -> dict[str, bytes]:
    """Verify, decrypt and unpack the encrypted package at *path*.

    *player_kem_private_key* is the player's ML-KEM-768 key, needed when the
    package is sealed for it with the hybrid wrap; *require_hybrid* refuses one
    sealed with RSA-OAEP alone (ADR-0012).

    Returns the decrypted entries keyed by archive path, sealed-checksum verified
    and shown to be the content the signed manifest describes.
    """
    if player_private_key is None:
        raise ValueError(f"Package {path.name!r} is encrypted — provide --player-keys to load it.")

    manifest = verify_manifest(path, compiler_public_key)
    players = manifest.get("security", {}).get("authorized_players", [])
    if not players:
        raise ValueError("Encrypted .tck has no authorized_players in manifest.")

    with zipfile.ZipFile(path, "r") as archive:
        blob = base64.b64decode(archive.read(PAYLOAD_ENTRY))
    content_key = content_key_for(
        players, player_private_key, player_kem_private_key, require_hybrid=require_hybrid
    )
    tar_bytes = decrypt_payload(content_key, blob[:12], blob[12:])

    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
        entries = {
            member.name: (tf.extractfile(member) or io.BytesIO()).read()
            for member in tf.getmembers()
            if member.isfile()
        }

    package_digest.verify(entries)
    _require_described_content(manifest, entries)
    return entries


def _require_described_content(manifest: dict, entries: dict[str, bytes]) -> None:
    """Refuse a payload whose sealed checksum is not the one the signed manifest states.

    The signature binds the manifest to ``payload.enc``; this binds the
    manifest's ``package.checksum`` to what that payload decrypts to, so the
    readable manifest's account of the package is the package.
    """
    inner = yaml.safe_load(entries[package_digest.MANIFEST_ENTRY]) or {}
    stated = manifest.get("package", {}).get("checksum")
    actual = inner.get("package", {}).get("checksum")
    if stated != actual:
        raise ValueError(
            "The package manifest does not describe its payload: it states checksum "
            f"{stated}, and the decrypted content is sealed with {actual}."
        )


def engine_package_keys(config: TestlabConfig, package: Path) -> PackageKeys:
    """Resolve the keys an encrypted *package* needs from this engine's config.

    A server cannot be handed a player's private key per request, and should
    not be: the engine *is* the player, so its identity lives in ``keys_dir``
    and the compilers it accepts in ``trust_store_dir``. The CLI passes the
    same two keys explicitly with ``--player-keys`` and ``--compiler-pub``.
    """
    private_key = config.keys_dir / f"{ENCRYPTION_KEY}.pem"
    if not private_key.is_file():
        raise ValueError(
            f"Package {package.name!r} is encrypted, and this engine has no player "
            f"identity: {private_key} does not exist. Generate one with "
            f"`testlab keygen` and point TESTLAB_KEYS_DIR at the directory holding "
            f"its encryption.pem."
        )

    compiler_id = encrypted_package_compiler_id(package)
    compiler_key = TrustStore(config.trust_store_dir).find(compiler_id)
    if compiler_key is None:
        raise ValueError(
            f"Package {package.name!r} is signed by compiler {compiler_id[:16]}, "
            f"which this engine does not trust. Copy that compiler's signing.pub "
            f"into {config.trust_store_dir}."
        )

    keys = PackageKeys(compiler_public_key=compiler_key)
    keys.update(decryption_keys(config.keys_dir))
    return keys

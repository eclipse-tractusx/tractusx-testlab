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
from tractusx_testlab.security.crypto.encryption import decrypt_package, wrapped_key_for
from tractusx_testlab.security.crypto.signing import package_signing_message, verify_signature

#: Archive entries of an encrypted package.
MANIFEST_ENTRY = "manifest.yaml"
PAYLOAD_ENTRY = "payload.enc"
SIGNATURE_ENTRY = "signature.sig"


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
) -> dict[str, bytes]:
    """Verify, decrypt and unpack the encrypted package at *path*.

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
    enc_key = wrapped_key_for(players, player_private_key)
    tar_bytes = decrypt_package(enc_key, blob[:12], blob[12:], player_private_key)

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

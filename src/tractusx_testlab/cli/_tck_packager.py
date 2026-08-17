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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Helpers for building encrypted .tck archives (payload.enc + signature.sig format)."""

from __future__ import annotations

import base64
import io
import tarfile
import zipfile
from pathlib import Path

import yaml

from tractusx_testlab.security.crypto.encryption import encrypt_for_recipients


def create_tar_bytes(source_dir: Path) -> bytes:
    """Create a gzip-compressed TAR of *source_dir* in memory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(source_dir, arcname=".")
    return buf.getvalue()


def build_encrypted_payload(
    tar_bytes: bytes,
    recipient_keys: dict[str, bytes],
) -> tuple[str, list[dict]]:
    """Encrypt *tar_bytes* with a single AES key wrapped for each recipient.

    Returns:
        (payload_b64, authorized_players) where payload_b64 = base64(nonce + ciphertext)
    """
    nonce, ciphertext, key_blocks = encrypt_for_recipients(tar_bytes, recipient_keys)
    payload_b64 = base64.b64encode(nonce + ciphertext).decode()
    authorized_players = [
        {"player_id": pid, "encrypted_key": base64.b64encode(enc_key).decode()}
        for pid, enc_key in key_blocks
    ]
    return payload_b64, authorized_players


def build_redacted_manifest(
    manifest_dict: dict,
    compiler_id: str,
    authorized_players: list[dict],
    signature_b64: str,
) -> dict:
    """Build a manifest that omits test IDs and asset paths but keeps TCK identity metadata."""
    result: dict = {
        "kind": "manifest",
        "package": {
            "format": "tck",
            "format_version": manifest_dict["package"]["format_version"],
            "testlab": manifest_dict["package"]["testlab"],
            "checksum": manifest_dict["package"]["checksum"],
            "encrypted": True,
            "allow_asset_override": False,
        },
        "tck": manifest_dict.get("tck", {}),
        "compilation": {
            "compiled_at": manifest_dict["compilation"]["compiled_at"],
            "compiler_version": manifest_dict["compilation"]["compiler_version"],
            "fingerprint": manifest_dict["compilation"]["fingerprint"],
        },
        "security": {
            "algorithm": "AES-256-GCM",
            "key_derivation": "RSA-OAEP-SHA256",
            "compiler_id": compiler_id,
            "signature": signature_b64,
            "authorized_players": authorized_players,
        },
    }
    return result


def write_encrypted_tck(
    tck_path: Path,
    redacted_manifest: dict,
    payload_b64: str,
    signature_b64: str,
) -> None:
    """Write the encrypted .tck ZIP archive to *tck_path*."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.yaml",
            yaml.dump(redacted_manifest, default_flow_style=False, sort_keys=False),
        )
        zf.writestr("payload.enc", payload_b64)
        zf.writestr("signature.sig", signature_b64)
    tck_path.parent.mkdir(parents=True, exist_ok=True)
    tck_path.write_bytes(buf.getvalue())

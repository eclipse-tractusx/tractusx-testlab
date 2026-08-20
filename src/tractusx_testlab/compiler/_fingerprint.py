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

"""Compilation fingerprint — nonce, persistent Ed25519 public key, and blake2b checksum."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KEY_DIR = Path.home() / ".testlab"
_KEY_FILE = _KEY_DIR / "compiler.key"


def _blake2b_hex(data: bytes) -> str:
    """Compute blake2b-256 hex digest."""
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def _load_or_create_key() -> bytes:
    """Load persistent compiler key from ~/.testlab/compiler.key, creating if absent."""
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()

    _KEY_DIR.mkdir(parents=True, exist_ok=True)
    key_bytes = os.urandom(32)
    _KEY_FILE.write_bytes(key_bytes)
    _KEY_FILE.chmod(0o600)
    logger.info("Generated compiler key at %s", _KEY_FILE)
    return key_bytes


def build_fingerprint(execution_json_bytes: bytes) -> dict[str, Any]:
    """Build the fingerprint block for the compilation section.

    Args:
        execution_json_bytes: The raw bytes of tck-execution.json content.

    Returns:
        Dict with nonce, public_key, and checksum fields.
    """
    # Nonce: blake2b hash of 32 random bytes
    nonce_bytes = os.urandom(32)
    nonce = f"blake2b:{_blake2b_hex(nonce_bytes)}"

    # Public key: persistent Ed25519-style key (raw 32 bytes, base64-encoded)
    key_bytes = _load_or_create_key()
    public_key = f"ed25519:{base64.b64encode(key_bytes).decode('ascii')}"

    # Checksum: blake2b of execution JSON content
    checksum = f"blake2b:{_blake2b_hex(execution_json_bytes)}"

    return {
        "nonce": nonce,
        "public_key": public_key,
        "digest": checksum,
    }

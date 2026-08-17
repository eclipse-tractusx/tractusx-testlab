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

"""Ed25519 signing and verification for compiled test packages."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def sign_bytes(data: bytes, private_pem: bytes) -> bytes:
    """Sign *data* with an Ed25519 private key and return the 64-byte signature."""
    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Expected Ed25519 private key")
    return key.sign(data)


def verify_signature(data: bytes, signature: bytes, public_pem: bytes) -> bool:
    """Verify an Ed25519 signature. Returns True if valid, False otherwise."""
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Expected Ed25519 public key")
    try:
        key.verify(signature, data)
        return True
    except InvalidSignature:
        return False

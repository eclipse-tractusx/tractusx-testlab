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

"""AES-256-GCM symmetric encryption with RSA-OAEP key wrapping for packages."""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization

# AES-256 key length
_AES_KEY_LEN = 32
# GCM nonce length (96 bits recommended by NIST)
_NONCE_LEN = 12


def encrypt_package(plaintext: bytes, recipient_public_pem: bytes) -> tuple[bytes, bytes, bytes]:
    """Encrypt *plaintext* with AES-256-GCM, wrap the AES key with RSA-OAEP.

    Returns:
        (encrypted_key, nonce, ciphertext)
    """
    aes_key = os.urandom(_AES_KEY_LEN)
    nonce = os.urandom(_NONCE_LEN)

    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    rsa_pub = serialization.load_pem_public_key(recipient_public_pem)
    encrypted_key = rsa_pub.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return encrypted_key, nonce, ciphertext


def encrypt_for_recipients(
    plaintext: bytes,
    recipient_public_pems: dict[str, bytes],
) -> tuple[bytes, bytes, list[tuple[str, bytes]]]:
    """Encrypt *plaintext* once and wrap the AES key for each recipient.

    Returns:
        (nonce, ciphertext, [(player_id, encrypted_aes_key), ...])
    """
    aes_key = os.urandom(_AES_KEY_LEN)
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    key_blocks: list[tuple[str, bytes]] = []
    for player_id, pub_pem in recipient_public_pems.items():
        rsa_pub = serialization.load_pem_public_key(pub_pem)
        enc_key = rsa_pub.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        key_blocks.append((player_id, enc_key))
    return nonce, ciphertext, key_blocks


def decrypt_package(encrypted_key: bytes, nonce: bytes, ciphertext: bytes, private_pem: bytes) -> bytes:
    """Unwrap AES key with RSA-OAEP, then decrypt AES-256-GCM ciphertext."""
    rsa_priv = serialization.load_pem_private_key(private_pem, password=None)
    aes_key = rsa_priv.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ciphertext, None)

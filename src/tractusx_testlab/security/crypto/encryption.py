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

"""AES-256-GCM symmetric encryption with RSA-OAEP key wrapping for packages."""

from __future__ import annotations

import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# AES-256 key length
_AES_KEY_LEN = 32
# GCM nonce length (96 bits recommended by NIST)
_NONCE_LEN = 12


def _oaep() -> padding.OAEP:
    """The OAEP configuration every wrap and unwrap in this module uses.

    Stated once: a package encrypted under one padding and decrypted under
    another fails with a bare ``ValueError`` that says nothing about which half
    disagreed.
    """
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )


def _rsa_public_key(public_pem: bytes) -> RSAPublicKey:
    """Load *public_pem*, refusing anything that is not an RSA key.

    ``load_pem_public_key`` returns whichever key type the PEM held, and every
    caller here goes straight on to RSA-OAEP.  Handed an Ed25519 key — the
    other key type this project issues, and the neighbouring one in a player's
    key directory — the call would fail with ``AttributeError: 'Ed25519PublicKey'
    object has no attribute 'encrypt'`` from inside the crypto library.  Naming
    the mistake here is the same guard :mod:`~tractusx_testlab.security.crypto.signing`
    already applies to its Ed25519 keys.
    """
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, RSAPublicKey):
        raise TypeError(
            f"Expected an RSA public key for package encryption, got "
            f"{type(key).__name__}. Encryption keys are 'encryption.pub'; "
            f"'signing.pub' is the Ed25519 key used to sign, not to encrypt."
        )
    return key


def _rsa_private_key(private_pem: bytes) -> RSAPrivateKey:
    """Load *private_pem*, refusing anything that is not an RSA key."""
    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, RSAPrivateKey):
        raise TypeError(
            f"Expected an RSA private key to decrypt this package, got "
            f"{type(key).__name__}. Decryption keys are 'encryption.pem'; "
            f"'signing.pem' is the Ed25519 key used to sign, not to decrypt."
        )
    return key


def encrypt_package(plaintext: bytes, recipient_public_pem: bytes) -> tuple[bytes, bytes, bytes]:
    """Encrypt *plaintext* with AES-256-GCM, wrap the AES key with RSA-OAEP.

    Returns:
        (encrypted_key, nonce, ciphertext)
    """
    aes_key = os.urandom(_AES_KEY_LEN)
    nonce = os.urandom(_NONCE_LEN)

    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    encrypted_key = _rsa_public_key(recipient_public_pem).encrypt(aes_key, _oaep())
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
        enc_key = _rsa_public_key(pub_pem).encrypt(aes_key, _oaep())
        key_blocks.append((player_id, enc_key))
    return nonce, ciphertext, key_blocks


def decrypt_package(
    encrypted_key: bytes, nonce: bytes, ciphertext: bytes, private_pem: bytes
) -> bytes:
    """Unwrap AES key with RSA-OAEP, then decrypt AES-256-GCM ciphertext."""
    aes_key = _rsa_private_key(private_pem).decrypt(encrypted_key, _oaep())
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ciphertext, None)

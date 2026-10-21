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

"""AES-256-GCM payload encryption, its content key wrapped for each player.

How the content key is wrapped — RSA-OAEP, or RSA-OAEP + ML-KEM-768 — is
:mod:`~tractusx_testlab.security.crypto.key_wrap`'s; this module encrypts the
payload once and asks it for one entry per authorized player.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tractusx_testlab.security.crypto.key_wrap import (
    HYBRID_ALG,
    oaep,
    rsa_private_key,
    rsa_public_key,
    unwrap_hybrid,
    unwrap_rsa,
    wrap_hybrid,
    wrap_rsa,
)

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

    encrypted_key = rsa_public_key(recipient_public_pem).encrypt(aes_key, oaep())
    return encrypted_key, nonce, ciphertext


def encrypt_for_recipients(
    plaintext: bytes,
    recipient_public_pems: Mapping[str, bytes],
    recipient_kem_pems: Mapping[str, bytes] | None = None,
) -> tuple[bytes, bytes, list[dict[str, str]]]:
    """Encrypt *plaintext* once and wrap the AES key for each recipient.

    *recipient_public_pems* maps each player id to its RSA ``encryption.pub``;
    a player that also has an ML-KEM-768 key in *recipient_kem_pems* (same id)
    gets the hybrid wrap, any other the RSA-OAEP one.

    Returns:
        (nonce, ciphertext, authorized_players) — one manifest entry per player,
        ``player_id`` first, the wrap's fields after it.
    """
    kem_pems = recipient_kem_pems or {}
    unknown = set(kem_pems) - set(recipient_public_pems)
    if unknown:
        raise ValueError(
            f"ML-KEM keys were given for players with no RSA encryption key: "
            f"{', '.join(sorted(p[:16] for p in unknown))}."
        )
    aes_key = os.urandom(_AES_KEY_LEN)
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    authorized_players = []
    for player_id, pub_pem in recipient_public_pems.items():
        kem_pem = kem_pems.get(player_id)
        wrap = wrap_hybrid(aes_key, pub_pem, kem_pem) if kem_pem else wrap_rsa(aes_key, pub_pem)
        authorized_players.append({"player_id": player_id, **wrap})
    return nonce, ciphertext, authorized_players


def decrypt_package(
    encrypted_key: bytes, nonce: bytes, ciphertext: bytes, private_pem: bytes
) -> bytes:
    """Unwrap AES key with RSA-OAEP, then decrypt AES-256-GCM ciphertext."""
    aes_key = rsa_private_key(private_pem).decrypt(encrypted_key, oaep())
    return decrypt_payload(aes_key, nonce, ciphertext)


def decrypt_payload(content_key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """Decrypt an AES-256-GCM payload with its already unwrapped *content_key*."""
    return AESGCM(content_key).decrypt(nonce, ciphertext, None)


def _entry_for(authorized_players: list[dict], private_pem: bytes) -> dict:
    """The entry of *authorized_players* listed under the fingerprint of *private_pem*.

    Each authorized player has its own copy of the key, wrapped with its own
    public key and listed under its fingerprint. The loader used to unwrap the
    first entry whoever was asking, so a package compiled for several players
    opened for the first and failed with a bare "Decryption failed" for the rest.
    """
    from tractusx_testlab.security.crypto.keygen import fingerprint_of_private_key

    fingerprint = fingerprint_of_private_key(private_pem)
    for player in authorized_players:
        if player.get("player_id") == fingerprint:
            return player
    authorized = ", ".join(str(p.get("player_id", ""))[:16] for p in authorized_players)
    raise ValueError(
        f"This package was not compiled for this player: the key fingerprint "
        f"{fingerprint[:16]} is not among the authorized players ({authorized}). "
        f"Ask the compiler to add this player's encryption.pub with --player-pub."
    )


def wrapped_key_for(authorized_players: list[dict], private_pem: bytes) -> bytes:
    """Return the content key RSA-OAEP-wrapped for the holder of *private_pem* (format 1 only).

    A hybrid entry has no such key: open it with :func:`content_key_for`.
    """
    entry = _entry_for(authorized_players, private_pem)
    if "encrypted_key" not in entry:
        raise ValueError(
            f"This player's key is wrapped with {entry.get('alg')}; use content_key_for."
        )
    return base64.b64decode(entry["encrypted_key"])


def content_key_for(
    authorized_players: list[dict],
    private_pem: bytes,
    kem_private_pem: bytes | None = None,
    *,
    require_hybrid: bool = False,
) -> bytes:
    """Unwrap the content key the package holds for the player of *private_pem*.

    The entry's ``alg`` decides: the hybrid wrap needs *kem_private_pem* too, an
    entry without ``alg`` is RSA-OAEP. With *require_hybrid*, an RSA-only entry
    is refused — for a player that will not open what a quantum computer could.
    """
    entry = _entry_for(authorized_players, private_pem)
    alg = entry.get("alg")
    if alg == HYBRID_ALG:
        return unwrap_hybrid(entry, private_pem, kem_private_pem)
    if alg is not None:
        raise ValueError(f"Unknown key wrap {alg!r} for this player; expected {HYBRID_ALG}.")
    if require_hybrid:
        raise ValueError(
            f"This package is sealed for this player with RSA-OAEP only, and this player "
            f"requires the post-quantum hybrid wrap ({HYBRID_ALG}). Recompile it for the "
            f"player's encryption.pub with its encryption_pq.pub beside it."
        )
    return unwrap_rsa(entry, private_pem)

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Wrapping a package's content key for one player — RSA-OAEP, or RSA-OAEP + ML-KEM-768.

A package is encrypted once with a random AES-256 content key; each authorized
player gets that key wrapped for its own identity, as one entry of
``security.authorized_players`` (ADR-0012).

* **RSA-OAEP-SHA256** (format 1): the content key itself, RSA-OAEP-wrapped.
  Recoverable by whoever breaks the player's RSA key — which a quantum computer
  will, from the public key alone. A package recorded today can be opened then
  ("harvest now, decrypt later").
* **hybrid:RSA-OAEP-SHA256+ML-KEM-768** (format 2, hybrid): a random secret is
  RSA-OAEP-wrapped, an ML-KEM-768 (FIPS 203) secret is encapsulated, and the key
  that wraps the content key is derived from **both** with HKDF-SHA256. Opening
  it takes breaking RSA *and* ML-KEM — the hybrid BSI TR-02102-1 asks for while
  the post-quantum schemes are young.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey, MLKEM768PublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from tractusx_testlab.security.crypto.keygen import _fingerprint

#: ``key_derivation`` of an entry without an ``alg``: the content key, RSA-OAEP-wrapped.
RSA_OAEP_ALG = "RSA-OAEP-SHA256"
#: ``alg`` of a hybrid entry.
HYBRID_ALG = "hybrid:RSA-OAEP-SHA256+ML-KEM-768"

#: Prefixes the HKDF ``info``: a key derived here is bound to this use and format.
_KDF_CONTEXT = b"tractusx-testlab/tck-key-wrap/v2\x00"
_SECRET_LEN = 32
_NONCE_LEN = 12


def oaep() -> padding.OAEP:
    """The OAEP configuration every RSA wrap and unwrap uses.

    Stated once: a package encrypted under one padding and decrypted under
    another fails with a bare ``ValueError`` that says nothing about which half
    disagreed.
    """
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    )


def rsa_public_key(public_pem: bytes) -> RSAPublicKey:
    """Load *public_pem*, refusing anything that is not an RSA key.

    ``load_pem_public_key`` returns whichever key type the PEM held. Handed the
    Ed25519 ``signing.pub`` — the neighbouring file in a player's key directory —
    the RSA call would fail with ``AttributeError: 'Ed25519PublicKey' object has
    no attribute 'encrypt'`` from inside the crypto library.
    """
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, RSAPublicKey):
        raise TypeError(
            f"Expected an RSA public key for package encryption, got "
            f"{type(key).__name__}. Encryption keys are 'encryption.pub'; "
            f"'signing.pub' is the Ed25519 key used to sign, not to encrypt."
        )
    return key


def rsa_private_key(private_pem: bytes) -> RSAPrivateKey:
    """Load *private_pem*, refusing anything that is not an RSA key."""
    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, RSAPrivateKey):
        raise TypeError(
            f"Expected an RSA private key to decrypt this package, got "
            f"{type(key).__name__}. Decryption keys are 'encryption.pem'; "
            f"'signing.pem' is the Ed25519 key used to sign, not to decrypt."
        )
    return key


def _mlkem_public_key(public_pem: bytes) -> MLKEM768PublicKey:
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, MLKEM768PublicKey):
        raise TypeError(
            f"Expected an ML-KEM-768 public key ('encryption_pq.pub'), got {type(key).__name__}."
        )
    return key


def _mlkem_private_key(private_pem: bytes) -> MLKEM768PrivateKey:
    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, MLKEM768PrivateKey):
        raise TypeError(
            f"Expected an ML-KEM-768 private key ('encryption_pq.pem'), got {type(key).__name__}."
        )
    return key


def _kek(
    rsa_secret: bytes, kem_secret: bytes, rsa_ciphertext: bytes, kem_ciphertext: bytes, key_id: str
) -> bytes:
    """The key-encryption key: HKDF-SHA256 over both secrets, bound to both ciphertexts.

    Concatenating the shared secrets as the input keying material is the
    combiner NIST SP 800-56C and SP 800-227 describe; the ciphertexts and the
    ML-KEM key go into ``info`` so a secret cannot be replayed under another one.
    """
    info = (
        _KDF_CONTEXT
        + hashlib.sha256(rsa_ciphertext).digest()
        + hashlib.sha256(kem_ciphertext).digest()
        + key_id.encode()
    )
    return HKDF(algorithm=hashes.SHA256(), length=_SECRET_LEN, salt=None, info=info).derive(
        rsa_secret + kem_secret
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def wrap_rsa(content_key: bytes, rsa_public_pem: bytes) -> dict[str, str]:
    """The format-1 entry fields: *content_key* RSA-OAEP-wrapped."""
    return {"encrypted_key": _b64(rsa_public_key(rsa_public_pem).encrypt(content_key, oaep()))}


def wrap_hybrid(content_key: bytes, rsa_public_pem: bytes, kem_public_pem: bytes) -> dict[str, str]:
    """The format-2 entry fields: *content_key* under a key derived from RSA-OAEP and ML-KEM-768."""
    rsa_secret = os.urandom(_SECRET_LEN)
    rsa_ciphertext = rsa_public_key(rsa_public_pem).encrypt(rsa_secret, oaep())
    kem_secret, kem_ciphertext = _mlkem_public_key(kem_public_pem).encapsulate()
    key_id = _fingerprint(kem_public_pem)
    kek = _kek(rsa_secret, kem_secret, rsa_ciphertext, kem_ciphertext, key_id)
    nonce = os.urandom(_NONCE_LEN)
    wrapped = AESGCM(kek).encrypt(nonce, content_key, HYBRID_ALG.encode())
    return {
        "alg": HYBRID_ALG,
        "rsa_ciphertext": _b64(rsa_ciphertext),
        "kem_key_id": key_id,
        "kem_ciphertext": _b64(kem_ciphertext),
        "wrapped_key": _b64(nonce + wrapped),
    }


def unwrap_rsa(entry: dict, rsa_private_pem: bytes) -> bytes:
    """The content key of a format-1 *entry*."""
    return rsa_private_key(rsa_private_pem).decrypt(
        base64.b64decode(entry["encrypted_key"]), oaep()
    )


def unwrap_hybrid(entry: dict, rsa_private_pem: bytes, kem_private_pem: bytes | None) -> bytes:
    """The content key of a format-2 *entry*; needs the player's RSA *and* ML-KEM key."""
    if kem_private_pem is None:
        raise ValueError(
            f"This package is sealed for this player with {HYBRID_ALG}, and no ML-KEM "
            f"key was supplied. Provide the player's encryption_pq.pem beside encryption.pem."
        )
    kem_key = _mlkem_private_key(kem_private_pem)
    key_id = _fingerprint(
        kem_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    if key_id != entry.get("kem_key_id"):
        raise ValueError(
            f"This package was sealed for ML-KEM key {str(entry.get('kem_key_id'))[:16]}, "
            f"and the supplied encryption_pq.pem is {key_id[:16]}."
        )
    rsa_ciphertext = base64.b64decode(entry["rsa_ciphertext"])
    kem_ciphertext = base64.b64decode(entry["kem_ciphertext"])
    rsa_secret = rsa_private_key(rsa_private_pem).decrypt(rsa_ciphertext, oaep())
    kek = _kek(
        rsa_secret, kem_key.decapsulate(kem_ciphertext), rsa_ciphertext, kem_ciphertext, key_id
    )
    blob = base64.b64decode(entry["wrapped_key"])
    return AESGCM(kek).decrypt(blob[:_NONCE_LEN], blob[_NONCE_LEN:], HYBRID_ALG.encode())


def key_derivation_of(authorized_players: list[dict]) -> str:
    """The manifest's ``security.key_derivation``: every wrap its entries use, comma-separated."""
    return ", ".join(sorted({p.get("alg", RSA_OAEP_ALG) for p in authorized_players}))

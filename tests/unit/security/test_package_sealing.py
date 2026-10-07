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

"""The code that decides whether a package is authentic, tested.

``security/`` generates the keys, encrypts the payload and verifies the
signature that say a ``.tck`` is the one its compiler built — and it had no unit
tests at all. For a certification instrument that travels between organisations,
that is the code whose failure is least visible and most consequential.
"""

from __future__ import annotations

import pytest

from tractusx_testlab.compiler import package_digest
from tractusx_testlab.security.crypto.encryption import (
    decrypt_package,
    encrypt_for_recipients,
    encrypt_package,
)
from tractusx_testlab.security.crypto.keygen import (
    generate_ed25519_keypair,
    generate_rsa_keypair,
)
from tractusx_testlab.security.crypto.signing import sign_bytes, verify_signature

_PAYLOAD = b"the bytes a player will execute"


@pytest.fixture(scope="module")
def rsa_keys() -> tuple[bytes, bytes]:
    """An RSA keypair, as ``testlab keygen`` issues for encryption.

    2048 rather than the 4096 default: these tests generate several pairs and
    key generation dominates their runtime.
    """
    pair = generate_rsa_keypair(key_size=2048)
    return pair.private_bytes, pair.public_bytes


def _rsa() -> tuple[bytes, bytes]:
    pair = generate_rsa_keypair(key_size=2048)
    return pair.private_bytes, pair.public_bytes


def _ed25519() -> tuple[bytes, bytes]:
    pair = generate_ed25519_keypair()
    return pair.private_bytes, pair.public_bytes


class TestEncryption:
    def test_a_package_round_trips(self, rsa_keys: tuple[bytes, bytes]) -> None:
        private_pem, public_pem = rsa_keys
        encrypted_key, nonce, ciphertext = encrypt_package(_PAYLOAD, public_pem)

        assert decrypt_package(encrypted_key, nonce, ciphertext, private_pem) == _PAYLOAD

    def test_the_ciphertext_is_not_the_payload(self, rsa_keys: tuple[bytes, bytes]) -> None:
        _, public_pem = rsa_keys
        _, _, ciphertext = encrypt_package(_PAYLOAD, public_pem)

        assert _PAYLOAD not in ciphertext

    def test_a_tampered_ciphertext_is_refused(self, rsa_keys: tuple[bytes, bytes]) -> None:
        """AES-GCM authenticates; a flipped bit must not decrypt to anything."""
        private_pem, public_pem = rsa_keys
        encrypted_key, nonce, ciphertext = encrypt_package(_PAYLOAD, public_pem)
        flipped = bytearray(ciphertext)
        flipped[0] ^= 0x01

        with pytest.raises(Exception):
            decrypt_package(encrypted_key, nonce, bytes(flipped), private_pem)

    def test_the_wrong_recipient_cannot_read_it(self) -> None:
        _, theirs = _rsa()
        mine, _ = _rsa()
        encrypted_key, nonce, ciphertext = encrypt_package(_PAYLOAD, theirs)

        with pytest.raises(Exception):
            decrypt_package(encrypted_key, nonce, ciphertext, mine)

    def test_each_recipient_unwraps_the_same_payload(self) -> None:
        """One ciphertext, one wrapped key per player — that is the whole point."""
        first_priv, first_pub = _rsa()
        second_priv, second_pub = _rsa()

        nonce, ciphertext, blocks = encrypt_for_recipients(
            _PAYLOAD, {"first": first_pub, "second": second_pub}
        )
        wrapped = dict(blocks)

        assert decrypt_package(wrapped["first"], nonce, ciphertext, first_priv) == _PAYLOAD
        assert decrypt_package(wrapped["second"], nonce, ciphertext, second_priv) == _PAYLOAD

    def test_a_signing_key_is_refused_where_an_encryption_key_is_meant(self) -> None:
        """The two live side by side in a player's key directory.

        Handed the Ed25519 one, this used to fail inside the crypto library with
        ``'Ed25519PublicKey' object has no attribute 'encrypt'``.
        """
        _, signing_pub = _ed25519()

        with pytest.raises(TypeError, match="RSA public key"):
            encrypt_package(_PAYLOAD, signing_pub)


class TestSigning:
    def test_a_signature_verifies(self) -> None:
        private_pem, public_pem = _ed25519()

        assert verify_signature(_PAYLOAD, sign_bytes(_PAYLOAD, private_pem), public_pem)

    def test_a_signature_does_not_verify_other_bytes(self) -> None:
        private_pem, public_pem = _ed25519()
        signature = sign_bytes(_PAYLOAD, private_pem)

        assert not verify_signature(_PAYLOAD + b"!", signature, public_pem)

    def test_another_compilers_signature_does_not_verify(self) -> None:
        theirs_priv, _ = _ed25519()
        _, ours_pub = _ed25519()

        assert not verify_signature(_PAYLOAD, sign_bytes(_PAYLOAD, theirs_priv), ours_pub)


class TestPackageDigest:
    """What `seal` records, `verify` must be able to check — over every entry."""

    @staticmethod
    def _entries() -> dict[str, bytes]:
        return {
            "manifest.yaml": b"kind: manifest\n",
            "tck-execution.json": b'{"compiled_tests": []}',
            "tests/probe.yaml": b"syntax: v1-alpha\n",
        }

    def test_a_sealed_package_verifies(self) -> None:
        package_digest.verify(package_digest.seal(self._entries()))

    def test_an_edited_test_file_is_refused(self) -> None:
        """The file the player executes is inside the envelope."""
        sealed = package_digest.seal(self._entries())
        sealed["tests/probe.yaml"] += b"# appended\n"

        with pytest.raises(ValueError, match="checksum mismatch"):
            package_digest.verify(sealed)

    def test_a_renamed_entry_is_refused(self) -> None:
        """Names are digested too, so a swap under a trusted name is caught."""
        sealed = package_digest.seal(self._entries())
        sealed["tests/other.yaml"] = sealed.pop("tests/probe.yaml")

        with pytest.raises(ValueError, match="checksum mismatch"):
            package_digest.verify(sealed)

    def test_a_removed_entry_is_refused(self) -> None:
        """Deleting a file used to skip verification rather than fail it."""
        sealed = package_digest.seal(self._entries())
        del sealed["tck-execution.json"]

        with pytest.raises(ValueError, match="checksum mismatch"):
            package_digest.verify(sealed)

    def test_a_package_with_no_manifest_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no manifest.yaml"):
            package_digest.verify({"tests/probe.yaml": b""})

    def test_a_package_with_no_recorded_digest_is_refused(self) -> None:
        """A package carrying no checksum cannot be shown to be the compiled one."""
        with pytest.raises(ValueError, match="no checksum"):
            package_digest.verify({"manifest.yaml": b"kind: manifest\n"})

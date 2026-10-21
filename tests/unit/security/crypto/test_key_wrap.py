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

"""The post-quantum hybrid key wrap (ADR-0012), tested.

A player with an ML-KEM-768 key gets the content key under a key derived from
RSA-OAEP *and* ML-KEM-768; one without keeps the RSA-OAEP wrap. Every package
sealed before the hybrid wrap must keep opening, and a player that requires the
hybrid must refuse one that is not.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidTag

from tractusx_testlab.security.crypto.encryption import (
    content_key_for,
    decrypt_payload,
    encrypt_for_recipients,
    wrapped_key_for,
)
from tractusx_testlab.security.crypto.key_wrap import (
    HYBRID_ALG,
    RSA_OAEP_ALG,
    key_derivation_of,
)
from tractusx_testlab.security.crypto.keygen import (
    KeyPair,
    generate_mlkem_keypair,
    generate_rsa_keypair,
)

_PAYLOAD = b"the bytes a player will execute"


@pytest.fixture(scope="module")
def hybrid_player() -> tuple[KeyPair, KeyPair]:
    """An RSA pair (2048: key generation dominates the runtime) and an ML-KEM-768 pair."""
    return generate_rsa_keypair(key_size=2048), generate_mlkem_keypair()


@pytest.fixture(scope="module")
def legacy_player() -> KeyPair:
    """A player identity from before the hybrid wrap: RSA only."""
    return generate_rsa_keypair(key_size=2048)


def _seal(*players: tuple[KeyPair, KeyPair | None]) -> tuple[bytes, bytes, list[dict]]:
    rsa = {pair.fingerprint: pair.public_bytes for pair, _ in players}
    kem = {pair.fingerprint: pq.public_bytes for pair, pq in players if pq is not None}
    return encrypt_for_recipients(_PAYLOAD, rsa, kem)


def _flip(value: str) -> str:
    raw = bytearray(base64.b64decode(value))
    raw[0] ^= 0x01
    return base64.b64encode(bytes(raw)).decode()


class TestHybridWrap:
    def test_a_hybrid_package_round_trips(self, hybrid_player: tuple[KeyPair, KeyPair]) -> None:
        rsa, pq = hybrid_player
        nonce, ciphertext, players = _seal((rsa, pq))

        content_key = content_key_for(players, rsa.private_bytes, pq.private_bytes)

        assert decrypt_payload(content_key, nonce, ciphertext) == _PAYLOAD

    def test_the_hybrid_entry_names_its_wrap_and_carries_no_rsa_only_key(
        self, hybrid_player: tuple[KeyPair, KeyPair]
    ) -> None:
        rsa, pq = hybrid_player
        (entry,) = _seal((rsa, pq))[2]

        assert entry["alg"] == HYBRID_ALG
        assert entry["kem_key_id"] == pq.fingerprint
        assert "encrypted_key" not in entry

    def test_hybrid_and_legacy_players_open_the_same_package(
        self, hybrid_player: tuple[KeyPair, KeyPair], legacy_player: KeyPair
    ) -> None:
        rsa, pq = hybrid_player
        nonce, ciphertext, players = _seal((rsa, pq), (legacy_player, None))

        hybrid_key = content_key_for(players, rsa.private_bytes, pq.private_bytes)
        legacy_key = content_key_for(players, legacy_player.private_bytes)

        assert decrypt_payload(hybrid_key, nonce, ciphertext) == _PAYLOAD
        assert decrypt_payload(legacy_key, nonce, ciphertext) == _PAYLOAD
        assert key_derivation_of(players) == f"{RSA_OAEP_ALG}, {HYBRID_ALG}"

    def test_a_legacy_entry_is_unchanged_from_format_1(self, legacy_player: KeyPair) -> None:
        """Older players read ``encrypted_key`` and nothing else."""
        (entry,) = _seal((legacy_player, None))[2]

        assert set(entry) == {"player_id", "encrypted_key"}
        assert key_derivation_of([entry]) == RSA_OAEP_ALG

    @pytest.mark.parametrize("field", ["kem_ciphertext", "rsa_ciphertext", "wrapped_key"])
    def test_a_tampered_wrap_is_refused(
        self, hybrid_player: tuple[KeyPair, KeyPair], field: str
    ) -> None:
        """Each part of the wrap goes into the key-encryption key; none can change."""
        rsa, pq = hybrid_player
        (entry,) = _seal((rsa, pq))[2]
        entry[field] = _flip(entry[field])

        with pytest.raises((InvalidTag, ValueError)):
            content_key_for([entry], rsa.private_bytes, pq.private_bytes)

    def test_without_the_ml_kem_key_the_player_is_told_what_is_missing(
        self, hybrid_player: tuple[KeyPair, KeyPair]
    ) -> None:
        rsa, pq = hybrid_player
        players = _seal((rsa, pq))[2]

        with pytest.raises(ValueError, match="encryption_pq.pem"):
            content_key_for(players, rsa.private_bytes)

    def test_another_ml_kem_key_is_refused_by_its_id(
        self, hybrid_player: tuple[KeyPair, KeyPair]
    ) -> None:
        rsa, pq = hybrid_player
        players = _seal((rsa, pq))[2]

        with pytest.raises(ValueError, match="sealed for ML-KEM key"):
            content_key_for(players, rsa.private_bytes, generate_mlkem_keypair().private_bytes)

    def test_the_rsa_only_accessor_names_the_hybrid_wrap(
        self, hybrid_player: tuple[KeyPair, KeyPair]
    ) -> None:
        rsa, pq = hybrid_player
        players = _seal((rsa, pq))[2]

        with pytest.raises(ValueError, match="content_key_for"):
            wrapped_key_for(players, rsa.private_bytes)

    def test_an_unknown_wrap_is_refused(self, legacy_player: KeyPair) -> None:
        (entry,) = _seal((legacy_player, None))[2]
        entry["alg"] = "ROT13"

        with pytest.raises(ValueError, match="Unknown key wrap"):
            content_key_for([entry], legacy_player.private_bytes)

    def test_an_ml_kem_key_for_a_player_not_listed_is_refused(
        self, hybrid_player: tuple[KeyPair, KeyPair]
    ) -> None:
        _, pq = hybrid_player

        with pytest.raises(ValueError, match="no RSA encryption key"):
            encrypt_for_recipients(_PAYLOAD, {}, {"stranger": pq.public_bytes})


class TestRequireHybrid:
    def test_a_player_requiring_the_hybrid_refuses_rsa_only(self, legacy_player: KeyPair) -> None:
        players = _seal((legacy_player, None))[2]

        with pytest.raises(ValueError, match="RSA-OAEP only"):
            content_key_for(players, legacy_player.private_bytes, require_hybrid=True)

    def test_a_player_requiring_the_hybrid_opens_a_hybrid_package(
        self, hybrid_player: tuple[KeyPair, KeyPair]
    ) -> None:
        rsa, pq = hybrid_player
        nonce, ciphertext, players = _seal((rsa, pq))

        key = content_key_for(players, rsa.private_bytes, pq.private_bytes, require_hybrid=True)

        assert decrypt_payload(key, nonce, ciphertext) == _PAYLOAD

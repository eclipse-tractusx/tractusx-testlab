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

"""A player identity with and without its ML-KEM-768 pair (ADR-0012).

Identities issued before the hybrid key wrap have no ``encryption_pq`` pair and
must keep loading; ``testlab keygen`` adds one to them without touching the
keys the player already handed out.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from tractusx_testlab.cli import app
from tractusx_testlab.security.crypto.keygen import (
    generate_ed25519_keypair,
    generate_rsa_keypair,
)
from tractusx_testlab.security.trust.identity import (
    PlayerIdentity,
    decryption_keys,
    pq_public_key_beside,
)


@pytest.fixture()
def legacy_dir(tmp_path: Path) -> Path:
    """An identity directory as ``testlab keygen`` wrote it before the hybrid wrap."""
    directory = tmp_path / "player"
    PlayerIdentity(
        encryption=generate_rsa_keypair(key_size=2048), signing=generate_ed25519_keypair()
    ).save(directory)
    return directory


class TestIdentity:
    def test_a_legacy_directory_loads_without_the_ml_kem_pair(self, legacy_dir: Path) -> None:
        assert PlayerIdentity.load(legacy_dir).pq_encryption is None

    def test_the_ml_kem_pair_is_saved_and_loaded(self, legacy_dir: Path) -> None:
        identity = PlayerIdentity.load(legacy_dir).with_pq_encryption()
        identity.save(legacy_dir)

        assert PlayerIdentity.load(legacy_dir) == identity

    def test_with_pq_encryption_keeps_an_existing_pair(self, legacy_dir: Path) -> None:
        identity = PlayerIdentity.load(legacy_dir).with_pq_encryption()

        assert identity.with_pq_encryption() is identity

    def test_decryption_keys_include_the_ml_kem_key_only_when_present(
        self, legacy_dir: Path
    ) -> None:
        assert set(decryption_keys(legacy_dir)) == {"player_private_key"}

        PlayerIdentity.load(legacy_dir).with_pq_encryption().save(legacy_dir)

        assert set(decryption_keys(legacy_dir)) == {"player_private_key", "player_kem_private_key"}


class TestPqPublicKeyBeside:
    def test_encryption_pub_pairs_with_encryption_pq_pub(self, tmp_path: Path) -> None:
        (tmp_path / "encryption.pub").write_bytes(b"rsa")
        (tmp_path / "encryption_pq.pub").write_bytes(b"kem")

        assert pq_public_key_beside(tmp_path / "encryption.pub") == b"kem"

    def test_a_renamed_key_pairs_by_its_own_name(self, tmp_path: Path) -> None:
        """A compiler's collection of players' keys must not hand one player another's."""
        (tmp_path / "acme.pub").write_bytes(b"rsa")
        (tmp_path / "other.pub").write_bytes(b"rsa")
        (tmp_path / "acme_pq.pub").write_bytes(b"kem")

        assert pq_public_key_beside(tmp_path / "acme.pub") == b"kem"
        assert pq_public_key_beside(tmp_path / "other.pub") is None


class TestKeygen:
    def test_keygen_writes_all_three_pairs(self, tmp_path: Path) -> None:
        result = CliRunner().invoke(app, ["keygen", "-o", str(tmp_path), "-l", "p"])

        assert result.exit_code == 0, result.output
        assert PlayerIdentity.load(tmp_path / "p").pq_encryption is not None

    def test_keygen_adds_the_ml_kem_pair_to_an_existing_identity(self, legacy_dir: Path) -> None:
        before = PlayerIdentity.load(legacy_dir)

        result = CliRunner().invoke(app, ["keygen", "-o", str(legacy_dir.parent), "-l", "player"])
        after = PlayerIdentity.load(legacy_dir)

        assert result.exit_code == 0, result.output
        assert "Added the ML-KEM-768 pair" in result.output
        assert (after.encryption, after.signing) == (before.encryption, before.signing)
        assert after.pq_encryption is not None

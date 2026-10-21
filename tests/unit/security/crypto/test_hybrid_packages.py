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

"""An encrypted ``.tck`` sealed with the hybrid key wrap, loaded end to end (ADR-0012).

Built with the packager's own functions and opened by the loader and the
engine's key resolution, so the two cannot disagree on the hybrid format
without these tests failing.
"""

from __future__ import annotations

import base64
import zipfile
from pathlib import Path

import pytest
import yaml

from tractusx_testlab.cli._tck_packager import (
    build_encrypted_payload,
    build_redacted_manifest,
    create_tar_bytes,
    sealed_entries,
    write_encrypted_tck,
)
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.security.crypto.key_wrap import HYBRID_ALG
from tractusx_testlab.security.crypto.keygen import (
    KeyPair,
    generate_ed25519_keypair,
    generate_mlkem_keypair,
    generate_rsa_keypair,
)
from tractusx_testlab.security.crypto.signing import package_signing_message, sign_bytes
from tractusx_testlab.security.trust.identity import PlayerIdentity

_MANIFEST_YAML = """\
kind: manifest
package: {format: tck, format_version: "1.0", testlab: 1.0.0a21, checksum: ""}
tck: {id: tck-hybrid}
compilation: {compiled_at: "2026-10-21T00:00:00Z", compiler_version: 1.0.0a21, fingerprint: {}}
"""

_TCK_BUNDLE_YAML = """\
syntax: v1-alpha
kind: tck
id: tck-hybrid
metadata: {name: Hybrid TCK, version: "1.0"}
tests:
  - id: smoke.yaml
"""

_TEST_YAML = """\
syntax: v1-alpha
kind: test
id: smoke
namespace: testlab.test
metadata: {name: Smoke, version: "1.0"}
execution:
  - uses: util/generate_uuid
    name: Generate UUID
"""


@pytest.fixture(scope="module")
def compiler() -> KeyPair:
    return generate_ed25519_keypair()


@pytest.fixture(scope="module")
def player() -> PlayerIdentity:
    """A player with the ML-KEM-768 pair (RSA 2048: key generation dominates the runtime)."""
    return PlayerIdentity(
        encryption=generate_rsa_keypair(key_size=2048),
        signing=generate_ed25519_keypair(),
        pq_encryption=generate_mlkem_keypair(),
    )


def _package(path: Path, compiler: KeyPair, player: PlayerIdentity, hybrid: bool) -> Path:
    """Seal, encrypt and sign a one-test package for *player*, as ``testlab compile`` does."""
    source = path.parent / f"{path.stem}-src"
    (source / "tests").mkdir(parents=True)
    (source / "manifest.yaml").write_text(_MANIFEST_YAML)
    (source / "tck-bundle.yaml").write_text(_TCK_BUNDLE_YAML)
    (source / "tests" / "smoke.yaml").write_text(_TEST_YAML)
    entries = sealed_entries(source)
    fingerprint = player.encryption.fingerprint
    kem = (
        {fingerprint: player.pq_encryption.public_bytes} if hybrid and player.pq_encryption else {}
    )
    payload_b64, players = build_encrypted_payload(
        create_tar_bytes(entries), {fingerprint: player.encryption.public_bytes}, kem
    )
    inner = yaml.safe_load(entries["manifest.yaml"])
    manifest = yaml.dump(build_redacted_manifest(inner, compiler.fingerprint, players)).encode()
    signature = sign_bytes(
        package_signing_message(manifest, payload_b64.encode()), compiler.private_bytes
    )
    write_encrypted_tck(path, manifest, payload_b64, base64.b64encode(signature).decode())
    return path


def _engine(
    tmp_path: Path, compiler: KeyPair, player: PlayerIdentity, **settings: bool
) -> TestlabPlayer:
    """An engine whose ``keys_dir`` holds *player* and whose trust store holds *compiler*."""
    player.save(tmp_path / "keys")
    (tmp_path / "trusted").mkdir()
    (tmp_path / "trusted" / "compiler.pub").write_bytes(compiler.public_bytes)
    config = TestlabConfig(
        keys_dir=tmp_path / "keys", trust_store_dir=tmp_path / "trusted", **settings
    )
    return TestlabPlayer(config=config)


class TestHybridPackage:
    def test_a_hybrid_package_loads_with_the_engines_keys(
        self, tmp_path: Path, compiler: KeyPair, player: PlayerIdentity
    ) -> None:
        package = _package(tmp_path / "p.tck", compiler, player, hybrid=True)
        keys = _engine(tmp_path, compiler, player)._package_keys(package)

        assert Loader().load(package, **keys).id == "tck-hybrid"

    def test_the_engine_resolves_the_ml_kem_key_from_keys_dir(
        self, tmp_path: Path, compiler: KeyPair, player: PlayerIdentity
    ) -> None:
        package = _package(tmp_path / "p.tck", compiler, player, hybrid=True)

        keys = _engine(tmp_path, compiler, player)._package_keys(package)

        assert player.pq_encryption is not None
        assert keys.get("player_kem_private_key") == player.pq_encryption.private_bytes

    def test_the_readable_manifest_names_the_wrap(
        self, tmp_path: Path, compiler: KeyPair, player: PlayerIdentity
    ) -> None:
        package = _package(tmp_path / "p.tck", compiler, player, hybrid=True)
        with zipfile.ZipFile(package) as archive:
            security = yaml.safe_load(archive.read("manifest.yaml"))["security"]

        assert security["key_derivation"] == HYBRID_ALG
        assert security["authorized_players"][0]["alg"] == HYBRID_ALG


class TestRequirePqEncryption:
    async def test_an_engine_requiring_it_refuses_a_legacy_package(
        self, tmp_path: Path, compiler: KeyPair, player: PlayerIdentity
    ) -> None:
        package = _package(tmp_path / "legacy.tck", compiler, player, hybrid=False)
        engine = _engine(tmp_path, compiler, player, require_pq_encryption=True)

        with pytest.raises(ValueError, match="post-quantum hybrid wrap"):
            await engine.run(package)

    def test_by_default_a_legacy_package_still_opens(
        self, tmp_path: Path, compiler: KeyPair, player: PlayerIdentity
    ) -> None:
        package = _package(tmp_path / "legacy.tck", compiler, player, hybrid=False)
        keys = _engine(tmp_path, compiler, player)._package_keys(package)

        assert Loader().load(package, **keys).id == "tck-hybrid"

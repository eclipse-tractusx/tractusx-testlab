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

"""An encrypted ``.tck`` opens for every player it was compiled for.

``1.0.0a3`` shipped three defects that together meant no encrypted package ever
loaded: the payload's TAR members were named ``./<path>``, the payload was never
sealed, and the loader unwrapped the first player's key whoever was asking. The
package here is built with the packager's own functions, so these tests fail
the moment the packager and the loader disagree again.

The readable ``manifest.yaml`` is covered by the same signature as the payload,
and can be verified with the Compiler's public key alone.
"""

from __future__ import annotations

import base64
import io
import tarfile
import zipfile
from collections.abc import Callable
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
from tractusx_testlab.player.loading._encrypted import verify_manifest
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.security.crypto.keygen import (
    KeyPair,
    generate_ed25519_keypair,
    generate_rsa_keypair,
)
from tractusx_testlab.security.crypto.signing import package_signing_message, sign_bytes

_MANIFEST_YAML = """\
kind: manifest
package:
  format: tck
  format_version: "1.0"
  testlab: 1.0.0a3
  checksum: ""
tck:
  id: tck-encrypted
compilation:
  compiled_at: "2026-09-13T00:00:00Z"
  compiler_version: 1.0.0a3
  fingerprint: {digest: none}
"""

_TCK_BUNDLE_YAML = """\
syntax: v1-alpha
kind: tck
id: tck-encrypted
metadata:
  name: Encrypted TCK
  version: "1.0"
tests:
  - id: smoke.yaml
"""

_TEST_YAML = """\
syntax: v1-alpha
kind: test
id: smoke
namespace: testlab.test
metadata:
  name: Smoke
  version: "1.0"
execution:
  - uses: util/generate_uuid
    name: Generate UUID
"""


@pytest.fixture(scope="module")
def compiler() -> KeyPair:
    return generate_ed25519_keypair()


@pytest.fixture(scope="module")
def players() -> list[KeyPair]:
    """Three RSA identities: the first two are authorized, the third is not.

    2048 rather than the 4096 default, as key generation dominates the runtime.
    """
    return [generate_rsa_keypair(key_size=2048) for _ in range(3)]


@pytest.fixture(scope="module")
def payload_tar(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    source = tmp_path_factory.mktemp("compiled")
    (source / "manifest.yaml").write_text(_MANIFEST_YAML)
    (source / "tck-bundle.yaml").write_text(_TCK_BUNDLE_YAML)
    (source / "tests").mkdir()
    (source / "tests" / "smoke.yaml").write_text(_TEST_YAML)
    return create_tar_bytes(sealed_entries(source))


def _build(
    path: Path,
    payload_tar: bytes,
    compiler: KeyPair,
    players: list[KeyPair],
    edit_manifest: Callable[[dict], None] = lambda _: None,
) -> Path:
    """Encrypt and sign *payload_tar* the way ``_seal_and_encrypt`` does.

    *edit_manifest* changes the readable manifest **before** it is signed, for a
    Compiler that signs a manifest which misdescribes its payload.
    """
    payload_b64, authorized = build_encrypted_payload(
        payload_tar, {p.fingerprint: p.public_bytes for p in players[:2]}
    )
    with tarfile.open(fileobj=io.BytesIO(payload_tar), mode="r:gz") as tf:
        inner = yaml.safe_load(tf.extractfile("manifest.yaml").read())  # type: ignore[union-attr]
    redacted = build_redacted_manifest(inner, compiler.fingerprint, authorized)
    edit_manifest(redacted)
    manifest_bytes = yaml.dump(redacted, sort_keys=False).encode()
    message = package_signing_message(manifest_bytes, payload_b64.encode())
    signature = base64.b64encode(sign_bytes(message, compiler.private_bytes)).decode()
    write_encrypted_tck(path, manifest_bytes, payload_b64, signature)
    return path


def _rewrite_entry(package: Path, target: Path, name: str, content: bytes) -> Path:
    """Copy *package* to *target* with the entry *name* replaced — a tampered archive."""
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(target, "w") as out:
        for entry in source.namelist():
            out.writestr(entry, content if entry == name else source.read(entry))
    return target


@pytest.fixture(scope="module")
def package(
    tmp_path_factory: pytest.TempPathFactory,
    payload_tar: bytes,
    compiler: KeyPair,
    players: list[KeyPair],
) -> Path:
    """An encrypted ``.tck`` for ``players[0]`` and ``players[1]``."""
    return _build(
        tmp_path_factory.mktemp("dist") / "tck-encrypted.tck", payload_tar, compiler, players
    )


class TestPayload:
    def test_members_are_named_as_the_loader_looks_them_up(self, payload_tar: bytes) -> None:
        with tarfile.open(fileobj=io.BytesIO(payload_tar), mode="r:gz") as tf:
            names = tf.getnames()

        assert sorted(names) == ["manifest.yaml", "tck-bundle.yaml", "tests/smoke.yaml"]


class TestLoader:
    @pytest.mark.parametrize("index", [0, 1])
    def test_every_authorized_player_opens_the_package(
        self, package: Path, compiler: KeyPair, players: list[KeyPair], index: int
    ) -> None:
        tck = Loader().load(
            package,
            player_private_key=players[index].private_bytes,
            compiler_public_key=compiler.public_bytes,
        )

        assert tck.id == "tck-encrypted"

    def test_a_player_the_package_was_not_compiled_for_is_told_so(
        self, package: Path, compiler: KeyPair, players: list[KeyPair]
    ) -> None:
        with pytest.raises(ValueError, match="not compiled for this player"):
            Loader().load(
                package,
                player_private_key=players[2].private_bytes,
                compiler_public_key=compiler.public_bytes,
            )


class TestManifestIntegrity:
    """The manifest stays readable, and cannot change without the signature failing."""

    def test_the_manifest_verifies_with_the_compiler_key_alone(
        self, package: Path, compiler: KeyPair
    ) -> None:
        manifest = verify_manifest(package, compiler.public_bytes)

        assert manifest["tck"]["id"] == "tck-encrypted"
        assert "signature" not in manifest["security"]

    def test_an_edited_manifest_is_refused(
        self, tmp_path: Path, package: Path, compiler: KeyPair, players: list[KeyPair]
    ) -> None:
        with zipfile.ZipFile(package) as archive:
            manifest = yaml.safe_load(archive.read("manifest.yaml"))
        manifest["tck"]["id"] = "a-different-tck"
        tampered = _rewrite_entry(
            package, tmp_path / "tampered.tck", "manifest.yaml", yaml.dump(manifest).encode()
        )

        with pytest.raises(ValueError, match="signature verification failed"):
            verify_manifest(tampered, compiler.public_bytes)
        with pytest.raises(ValueError, match="signature verification failed"):
            Loader().load(
                tampered,
                player_private_key=players[0].private_bytes,
                compiler_public_key=compiler.public_bytes,
            )

    def test_an_edited_payload_is_refused_before_decryption(
        self, tmp_path: Path, package: Path, compiler: KeyPair
    ) -> None:
        tampered = _rewrite_entry(
            package, tmp_path / "tampered.tck", "payload.enc", base64.b64encode(b"x" * 64)
        )

        with pytest.raises(ValueError, match="signature verification failed"):
            verify_manifest(tampered, compiler.public_bytes)

    def test_a_signed_manifest_that_misdescribes_its_payload_is_refused(
        self, tmp_path: Path, payload_tar: bytes, compiler: KeyPair, players: list[KeyPair]
    ) -> None:
        def claim_another_checksum(manifest: dict) -> None:
            manifest["package"]["checksum"] = "blake2b:" + "0" * 64

        misdescribed = _build(
            tmp_path / "misdescribed.tck", payload_tar, compiler, players, claim_another_checksum
        )

        with pytest.raises(ValueError, match="does not describe its payload"):
            Loader().load(
                misdescribed,
                player_private_key=players[0].private_bytes,
                compiler_public_key=compiler.public_bytes,
            )


class TestServerSideKeys:
    """The engine resolves its own identity and trusted compilers from config."""

    def _player(self, tmp_path: Path) -> TestlabPlayer:
        return TestlabPlayer(
            config=TestlabConfig(keys_dir=tmp_path / "keys", trust_store_dir=tmp_path / "trusted")
        )

    def test_keys_come_from_keys_dir_and_the_trust_store(
        self, tmp_path: Path, package: Path, compiler: KeyPair, players: list[KeyPair]
    ) -> None:
        (tmp_path / "keys").mkdir()
        (tmp_path / "keys" / "encryption.pem").write_bytes(players[1].private_bytes)
        (tmp_path / "trusted").mkdir()
        (tmp_path / "trusted" / "compiler.pub").write_bytes(compiler.public_bytes)

        keys = self._player(tmp_path)._package_keys(package)
        tck = Loader().load(package, **keys)

        assert tck.id == "tck-encrypted"

    def test_an_engine_without_an_identity_refuses(self, tmp_path: Path, package: Path) -> None:
        with pytest.raises(ValueError, match="no player identity"):
            self._player(tmp_path)._package_keys(package)

    def test_an_untrusted_compiler_is_refused(
        self, tmp_path: Path, package: Path, players: list[KeyPair]
    ) -> None:
        (tmp_path / "keys").mkdir()
        (tmp_path / "keys" / "encryption.pem").write_bytes(players[0].private_bytes)

        with pytest.raises(ValueError, match="does not trust"):
            self._player(tmp_path)._package_keys(package)

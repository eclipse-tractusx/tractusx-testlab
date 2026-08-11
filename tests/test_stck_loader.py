################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Regression tests for .stck archive loading via Loader._load_package."""

from __future__ import annotations

from pathlib import Path

import pytest

from tractusx_testlab.compiler.packager import Packager
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.security.crypto import generate_ed25519_keypair, generate_rsa_keypair


_VALID_SCRIPT_YAML = b"""\
syntax: v1-alpha
kind: test
id: stck-smoke
namespace: testlab.test
dataspace_version: saturn
metadata:
  name: stck-smoke-test
  version: "1.0"
  description: A test packed into a .stck archive
execution:
  - id: step_one
    uses: precondition/provide
    with:
      value: hello
    returns:
      greeting: {type: string}
"""


@pytest.fixture()
def stck_archive(tmp_path: Path) -> tuple[Path, bytes, bytes]:
    """Build a .stck archive and return (archive_path, player_private_key, compiler_public_key)."""
    signing_kp = generate_ed25519_keypair()
    encryption_kp = generate_rsa_keypair(key_size=2048)

    output_path = tmp_path / "bundle.stck"
    Packager.build(
        script_yaml=_VALID_SCRIPT_YAML,
        compiler_signing_key=signing_kp.private_bytes,
        compiler_id=signing_kp.fingerprint,
        recipient_public_keys={"player-1": encryption_kp.public_bytes},
        output_path=output_path,
        name="stck-smoke-test",
        version="1.0",
    )
    return output_path, encryption_kp.private_bytes, signing_kp.public_bytes


class TestStckLoading:
    """Regression tests for .stck loading through Loader."""

    def test_load_stck_produces_valid_tck(
        self, stck_archive: tuple[Path, bytes, bytes],
    ) -> None:
        """A .stck archive round-trips through build → load correctly."""
        archive_path, player_priv, compiler_pub = stck_archive
        loader = Loader()

        tck = loader.load(archive_path, player_priv, compiler_pub)

        assert tck.name == "stck-smoke-test"
        assert tck.script_count() == 1

    def test_load_stck_preserves_step_definitions(
        self, stck_archive: tuple[Path, bytes, bytes],
    ) -> None:
        """Steps declared in the YAML survive the encrypt/decrypt round-trip."""
        archive_path, player_priv, compiler_pub = stck_archive
        loader = Loader()

        tck = loader.load(archive_path, player_priv, compiler_pub)
        script = tck.scripts[0]

        assert script.step_count() == 1
        assert script.steps[0].uses == "precondition/provide"

    def test_load_stck_without_keys_raises(self, stck_archive: tuple[Path, bytes, bytes]) -> None:
        """Loading a .stck without providing keys raises ValueError."""
        archive_path, _, _ = stck_archive
        loader = Loader()

        with pytest.raises(ValueError, match="player_private_key"):
            loader.load(archive_path)

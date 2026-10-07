################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Keys and run records are files only their owner can read, from the moment they exist.

Each case runs under a umask of ``0``, the most permissive a process can have:
a file that comes out ``0600`` there was given its mode when it was created,
not by the umask and not by a ``chmod`` after its content was written.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from tractusx_testlab.compiler import _fingerprint
from tractusx_testlab.security.crypto.keygen import generate_ed25519_keypair, save_keypair
from tractusx_testlab.security.private_files import (
    make_private_dirs,
    open_private,
    write_private_bytes,
)

_NO_FOLLOW = getattr(os, "O_NOFOLLOW", 0) != 0


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture(autouse=True)
def _permissive_umask() -> Iterator[None]:
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


class TestPrivateFiles:
    def test_a_record_is_created_0600_in_0700_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "logs" / "2026-10-01" / "run.log"

        with open_private(path) as handle:
            handle.write("line\n")

        assert _mode(path) == 0o600
        assert _mode(tmp_path / "logs") == 0o700
        assert _mode(tmp_path / "logs" / "2026-10-01") == 0o700

    def test_a_record_is_appended_to(self, tmp_path: Path) -> None:
        path = tmp_path / "run.log"
        for line in ("one\n", "two\n"):
            with open_private(path) as handle:
                handle.write(line)

        assert path.read_text() == "one\ntwo\n"

    def test_a_file_that_was_readable_is_narrowed_before_it_is_written(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "key.pem"
        path.write_bytes(b"old")
        path.chmod(0o644)

        write_private_bytes(path, b"secret")

        assert path.read_bytes() == b"secret"
        assert _mode(path) == 0o600

    def test_a_directory_that_exists_is_left_as_it_is(self, tmp_path: Path) -> None:
        shared = tmp_path / "shared"
        shared.mkdir(mode=0o755)

        write_private_bytes(shared / "inner" / "key.pem", b"secret")

        assert _mode(shared) == 0o755
        assert _mode(shared / "inner") == 0o700

    def test_making_directories_twice_is_harmless(self, tmp_path: Path) -> None:
        make_private_dirs(tmp_path / "a" / "b")
        make_private_dirs(tmp_path / "a" / "b")

        assert _mode(tmp_path / "a" / "b") == 0o700

    @pytest.mark.skipif(not _NO_FOLLOW, reason="the platform cannot refuse to follow a link")
    def test_a_link_planted_at_the_name_is_not_followed(self, tmp_path: Path) -> None:
        target = tmp_path / "elsewhere.txt"
        target.write_text("untouched")
        link = tmp_path / "key.pem"
        link.symlink_to(target)

        with pytest.raises(OSError):
            write_private_bytes(link, b"secret")

        assert target.read_text() == "untouched"


class TestKeys:
    def test_a_private_key_is_written_0600_in_a_0700_directory(self, tmp_path: Path) -> None:
        keys = tmp_path / "keys"

        save_keypair(generate_ed25519_keypair(), keys, "signing")

        assert _mode(keys / "signing.pem") == 0o600
        assert _mode(keys) == 0o700
        assert (keys / "signing.pub").read_bytes().startswith(b"-----BEGIN PUBLIC KEY-----")

    def test_a_private_key_written_over_a_readable_one_is_narrowed(self, tmp_path: Path) -> None:
        (tmp_path / "signing.pem").write_bytes(b"old")
        (tmp_path / "signing.pem").chmod(0o644)
        pair = generate_ed25519_keypair()

        save_keypair(pair, tmp_path, "signing")

        assert (tmp_path / "signing.pem").read_bytes() == pair.private_bytes
        assert _mode(tmp_path / "signing.pem") == 0o600

    def test_the_compilers_own_key_is_written_0600(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_fingerprint, "_KEY_DIR", tmp_path / ".testlab")
        monkeypatch.setattr(_fingerprint, "_KEY_FILE", tmp_path / ".testlab" / "compiler.key")

        key = _fingerprint._load_or_create_key()

        assert (tmp_path / ".testlab" / "compiler.key").read_bytes() == key
        assert _mode(tmp_path / ".testlab" / "compiler.key") == 0o600
        assert _mode(tmp_path / ".testlab") == 0o700

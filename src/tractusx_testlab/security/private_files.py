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

"""Files only the account running TestLab can read: its keys, and the records of a run.

A private key is a secret by definition, and a run's transcript, its execution
trace and its log carry what the run saw — request and response bodies, the
system under test's answers. They used to be created with whatever the
process's umask allowed, readable by every account on the host on most
systems. Here they are created ``0600``, and every directory TestLab creates on
the way ``0700``.

The mode is given when the file is created, never set after its content is
written: there is no moment at which the content sits in a file another account
may open. A file that already existed is narrowed to ``0600`` before anything is
written to it, and a symbolic link at the file's own name is refused rather than
followed, so a link planted where a key or a record will be written does not
redirect it. A directory that already exists is left as it is: it may be the
operator's own, shared on purpose.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import IO

#: The mode of every file this module creates: read and write for the owner only.
PRIVATE_FILE_MODE = 0o600
#: The mode of every directory this module creates: the owner only.
PRIVATE_DIR_MODE = 0o700

# Not on every platform; where they are missing the flag is simply not set.
_NO_FOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOSE_ON_EXEC = getattr(os, "O_CLOEXEC", 0)


def make_private_dirs(directory: Path) -> None:
    """Create *directory* and every missing parent of it, each one ``0700``.

    ``Path.mkdir(parents=True, mode=...)`` gives the mode to the last directory
    only and creates the parents with the default; this creates each one itself.
    """
    missing: list[Path] = []
    current = directory
    while not current.exists() and current.parent != current:
        missing.append(current)
        current = current.parent
    for path in reversed(missing):
        # Created meanwhile by someone else: it exists, which is all that is needed.
        with contextlib.suppress(FileExistsError):
            path.mkdir(mode=PRIVATE_DIR_MODE)


def open_private(path: Path, *, append: bool = True) -> IO[str]:
    """Open *path* to write text, as a file only its owner can read.

    Appends by default, as a run's records do; ``append=False`` starts the file
    over. Missing directories are created ``0700`` (:func:`make_private_dirs`).
    """
    fd = _open_private(path, os.O_APPEND if append else os.O_TRUNC)
    try:
        return os.fdopen(fd, "a" if append else "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise


def write_private_bytes(path: Path, data: bytes) -> None:
    """Write *data* to *path* — a key, typically — as a file only its owner can read."""
    with os.fdopen(_open_private(path, os.O_TRUNC), "wb") as handle:
        handle.write(data)


def _open_private(path: Path, mode_flag: int) -> int:
    """A descriptor open for writing on *path*, created — or narrowed to — ``0600``."""
    make_private_dirs(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | mode_flag | _NO_FOLLOW | _CLOSE_ON_EXEC
    fd = os.open(path, flags, PRIVATE_FILE_MODE)
    try:
        # A file that existed before keeps its mode through ``O_CREAT``.
        if hasattr(os, "fchmod"):
            os.fchmod(fd, PRIVATE_FILE_MODE)
    except BaseException:
        os.close(fd)
        raise
    return fd

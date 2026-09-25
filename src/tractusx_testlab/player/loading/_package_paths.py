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

"""Where a name inside a ``.tck`` package may point: inside the package, and nowhere else.

Every path the loader and the player build from package content — an archive
entry it writes, a ``tests:`` id it reads, a test data or schema ``source`` it
seeds — comes from whoever built the package, and a package travels between
organisations and arrives through an unauthenticated upload. Joined verbatim,
``../`` walks out of the extraction directory and an absolute name replaces it
altogether (``Path("/tmp/x") / "/home/u/.bashrc"`` is ``/home/u/.bashrc``), so
a package could write any file the engine user can — its trusted-compiler
store, a shell profile — and read any file into a request it sends.

A name is therefore checked before it is joined, and the joined path is checked
again after resolving, so neither a traversal nor a symbolic link on the way
leads out.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath


class UnsafePackagePathError(ValueError):
    """A name in a package that points outside it."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        super().__init__(f"Refusing package path {name!r}: {reason}.")


def package_path(base: Path, name: str) -> Path:
    """The path *name* names under *base* — or refuse a name that leaves it.

    Refused: an empty name, a NUL byte, a backslash (a Windows separator a
    POSIX join would keep as part of one name), an absolute path or a drive, a
    ``..`` segment, and anything that — symbolic links followed — resolves
    outside *base*.

    Raises:
        UnsafePackagePathError: for any of the above. A ``ValueError``, so every
            caller that already refuses a malformed package refuses this one too.
    """
    if not name or "\x00" in name:
        raise UnsafePackagePathError(name, "empty, or contains a NUL byte")
    if "\\" in name:
        raise UnsafePackagePathError(name, "contains a backslash")
    posix, windows = PurePosixPath(name), PureWindowsPath(name)
    if posix.is_absolute() or windows.drive or windows.root:
        raise UnsafePackagePathError(name, "absolute")
    if ".." in posix.parts:
        raise UnsafePackagePathError(name, "contains a '..' segment")

    target = base / posix
    if not target.resolve().is_relative_to(base.resolve()):
        raise UnsafePackagePathError(name, "resolves outside the package")
    return target

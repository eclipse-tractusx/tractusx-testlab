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

"""The run transcript — everything the console showed, in a file.

A per-logger file handler cannot be this. It only ever sees what was written
through *that* logger, which left the transcript holding the execution events
and nothing else: not the compile narration, not the run header, not the result
banner, and — worst of the four — not the tracebacks, because
``logger.exception`` goes to the root logger and ``typer.echo`` goes nowhere
near ``logging`` at all. A file that omits the traceback is missing the one
thing the reader opened it for.

So the transcript is taken where the console is: at ``sys.stdout`` and
``sys.stderr``. Whatever a run prints, by any route, is what the file gets —
which makes "the same as the console" a property of the mechanism rather than a
list of call sites somebody has to keep complete.

The file is plain text, so the ANSI colouring and the progress bar's redraws are
stripped on the way in. The console still gets them untouched.
"""

from __future__ import annotations

import re
import sys
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

#: SGR colours, cursor moves, and the rest of what a terminal renders rather
#: than shows. A transcript is read in an editor, where they are noise.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def new_run_id() -> str:
    """An id for one run, shared by its transcript, its trace, and its job."""
    return uuid.uuid4().hex


def transcript_path(logs_dir: Path, run_id: str, when: datetime | None = None) -> Path:
    """Where a run's transcript goes: ``<logs_dir>/<date>/<time>_<run_id>.log``.

    Deliberately the same date directory and the same ``<time>_<id>`` stem the
    trace uses under ``data_dir``, so the two records of one run sit at matching
    paths and are found together.
    """
    now = when or datetime.now(UTC)
    time_prefix = now.strftime("%H-%M-%S-") + f"{now.microsecond // 1000:03d}"
    return logs_dir / now.strftime("%Y-%m-%d") / f"{time_prefix}_{run_id}.log"


class _Tee:
    """Writes to the console as before, and to the transcript as plain text.

    Everything that is not ``write`` is delegated to the real stream, ``isatty``
    included: rich asks before it animates, and answering "no" because a file is
    attached would change what the operator sees on screen. The point is to copy
    the console, not to replace it.
    """

    __slots__ = ("_file", "_pending", "_stream")

    def __init__(self, stream: IO[str], file: IO[str]) -> None:
        self._stream = stream
        self._file = file
        self._pending = ""

    def write(self, text: str) -> int:
        written = self._stream.write(text)
        self._to_file(text)
        return written

    def _to_file(self, text: str) -> None:
        """Strip the terminal's own bookkeeping, then keep the words.

        A progress bar redraws by returning to the start of the line and writing
        over itself. Kept verbatim that is a hundred near-identical lines; only
        the last state of each line is what the operator actually read.
        """
        cleaned = _ANSI.sub("", text)
        if not cleaned:
            return
        self._pending += cleaned
        while True:
            index = self._pending.find("\n")
            if index < 0:
                break
            line, self._pending = self._pending[:index], self._pending[index + 1 :]
            self._file.write(line.rsplit("\r", 1)[-1] + "\n")
        self._file.flush()

    def flush(self) -> None:
        self._stream.flush()
        self._file.flush()

    def close(self) -> None:
        """Flush the last partial line; the streams themselves are not ours."""
        if self._pending:
            self._file.write(self._pending.rsplit("\r", 1)[-1] + "\n")
            self._pending = ""
        self._file.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


#: The transcript this process is currently taking, if it is taking one. Read by
#: the player so that a CLI run — which opens the transcript before compiling,
#: to catch the compiler's output — is not given a second one at job start.
_active: Path | None = None


def active() -> Path | None:
    """The transcript being written right now, or ``None``."""
    return _active


@contextmanager
def recording(path: Path | None) -> Iterator[Path | None]:
    """Copy everything printed inside this block into *path*.

    Nests safely: an inner call while a transcript is already open is a no-op
    rather than a second file, so a player run inside a CLI run keeps writing to
    the one transcript the operator was told about.
    """
    global _active
    if path is None or _active is not None:
        yield _active
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a", encoding="utf-8")
    out, err = _Tee(sys.stdout, handle), _Tee(sys.stderr, handle)
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    _active = path
    try:
        yield path
    finally:
        out.close()
        err.close()
        sys.stdout, sys.stderr = saved_out, saved_err
        _active = None
        handle.close()

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

"""Lines from stdin that a deadline and a stop can interrupt (``cli._terminal_operator``).

A choice put to the operator waits at most the step's timeout, and not at all
once the run ended or a Ctrl-C interrupted it. So a read never blocks longer
than :data:`SLICE_S` before it looks at both again — with ``select()`` where
stdin can be waited on, on a daemon thread where it cannot (a Windows console).
"""

from __future__ import annotations

import queue
import select
import sys
import threading
import time
from typing import IO

#: The longest a choice's read blocks before it looks at its deadline and its stop again.
SLICE_S = 0.2


def read_stdin(timeout: float | None, stop: threading.Event | None = None) -> str | None:
    """A line from stdin; ``None`` once *timeout* seconds passed, or *stop* was set, without one.

    ``timeout=None`` reads as long as it takes, on the calling thread: the
    approval, read before the event loop starts, where a Ctrl-C interrupts it.
    """
    if timeout is None:
        return sys.stdin.readline()
    deadline = time.monotonic() + max(timeout, 0.0)
    while stop is None or not stop.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        line = _poll(min(remaining, SLICE_S))
        if line is not None:
            return line
    return None


def _poll(wait: float) -> str | None:
    """A line, if one comes within *wait* seconds."""
    stream = sys.stdin
    try:
        stream.fileno()
    except (OSError, ValueError):  # in memory (a test's input): a read never blocks
        return stream.readline()
    try:
        ready, _, _ = select.select([stream], [], [], wait)
    except (OSError, ValueError):  # not selectable (a Windows console): a thread reads it
        return _queued(stream).get(wait)
    return stream.readline() if ready else None


class _QueuedStdin:
    """A stream read line by line on a daemon thread, for one ``select()`` cannot wait on.

    A daemon, so a read nobody is waiting for any more never holds the process
    open; a line typed after its question closed goes to the next one.
    """

    def __init__(self, stream: IO[str]) -> None:
        self.stream = stream
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._read, name="testlab-stdin", daemon=True)
        self._reader.start()

    def _read(self) -> None:
        while True:
            line = self.stream.readline()
            self._lines.put(line)
            if line == "":  # the end of the input
                return

    def get(self, wait: float) -> str | None:
        try:
            line = self._lines.get(timeout=wait)
        except queue.Empty:
            return None
        if line == "":
            self._lines.put(line)  # the input stays ended for whoever asks next
        return line


_reader: _QueuedStdin | None = None
_reader_lock = threading.Lock()


def _queued(stream: IO[str]) -> _QueuedStdin:
    """The reader of *stream*, started the first time it is needed."""
    global _reader
    with _reader_lock:
        if _reader is None or _reader.stream is not stream:
            _reader = _QueuedStdin(stream)
        return _reader

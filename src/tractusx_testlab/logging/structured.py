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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""The run's console transcript — the same lines on screen and on disk.

This used to write JSON-lines to the log file while the console got readable
text, which meant the file an operator opened to see what happened was the one
audience-mismatched artifact in the system: too verbose to read, and duplicating
what the execution trace already holds in a form tools actually parse.

The split is now by audience rather than by destination. This module writes the
transcript — text, identical to the console — under ``logs_dir``. The
machine-readable record is :mod:`tractusx_testlab.logging.trace`, which writes
CloudEvents under ``data_dir`` (ADR-0016).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import IO

from tractusx_testlab.logging.console import render


class _LazyStdout:
    """Stands in for ``sys.stdout``, resolved on every write."""

    def write(self, text: str) -> int:
        return sys.stdout.write(text)

    def flush(self) -> None:
        sys.stdout.flush()


def _readable(record: logging.LogRecord) -> logging.LogRecord:
    """A copy of *record* whose message is the rendered execution event.

    Shared by the console handler and the file handler so the transcript on disk
    is the transcript on screen — byte for byte, rather than two renderings that
    drift apart.
    """
    if not (hasattr(record, "extra_data") or (record.exc_info and record.exc_info[1])):
        return record
    record = logging.makeLogRecord(record.__dict__)
    if hasattr(record, "extra_data"):
        record.msg = render(record.getMessage(), dict(record.extra_data))
        record.args = None
    if record.exc_info and record.exc_info[1]:
        record.msg = record.getMessage() + f" exception:[{record.exc_info[1]}]"
        record.args = None
        record.exc_info = None
    return record


class CliHandler(logging.StreamHandler):
    """StreamHandler that formats structuredLogger records as human-readable text.
    Attach to any logger like a normal handler::

        handler = CliHandler()  # writes to stdout
        handler = CliHandler(sys.stderr)
        logger.addHandler(handler)
    """

    # Fallback used when no root console formatter is configured yet.
    _FALLBACK_FMT = "%(asctime)s [%(levelname)-8s] [%(name)-15s] %(message)s"
    _FALLBACK_DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, stream: IO | None = None) -> None:
        # Resolved at write time, not here: the run transcript replaces
        # ``sys.stdout`` while the engine is running, and a handler that had
        # already captured the original stream would write past it.
        super().__init__(stream or _LazyStdout())
        # Inherit the engine's console formatter so logging.yml changes apply here too.
        delegate = self._root_console_formatter()
        if delegate is not None:
            self.setFormatter(logging.Formatter(fmt=delegate._fmt, datefmt=delegate.datefmt))
        else:
            self.setFormatter(
                logging.Formatter(fmt=self._FALLBACK_FMT, datefmt=self._FALLBACK_DATEFMT)
            )

    @staticmethod
    def _root_console_formatter() -> logging.Formatter | None:
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and handler.formatter is not None:
                return handler.formatter
        return None

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(_readable(record))


class StructuredLogger:
    """Writes the run transcript to a stream and, per job, to a file.

    Log files are organised by date and named after the job::

        <logs_dir>/2026-03-30/11-56-35-777_<job_id>.log

    Usage::

        log = StructuredLogger("testlab.player", logs_dir=Path("~/.testlab/logs"))
        job_log = log.for_job("abc123")  # creates dated sub-dir + file
        job_log.info("Step started", step_index=0, step_type="create_asset")
    """

    __slots__ = ("_file_handler", "_logger", "_logs_dir")

    def __init__(
        self,
        name: str = "testlab",
        logs_dir: Path | None = None,
        log_file: Path | None = None,
        stream: IO | None = None,
        level: int = logging.DEBUG,
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.propagate = False
        self._file_handler: logging.FileHandler | None = None
        self._logs_dir = logs_dir

        # Always enable console output stream
        self._logger.addHandler(CliHandler(stream or sys.stdout))

        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setFormatter(
                logging.Formatter(
                    fmt=CliHandler._FALLBACK_FMT, datefmt=CliHandler._FALLBACK_DATEFMT
                )
            )
            self._logger.addHandler(file_handler)
            self._file_handler = file_handler

    def for_job(self, job_id: str) -> StructuredLogger:
        """Create a child logger named for the job, writing to the console.

        No file of its own: the run transcript is taken at ``sys.stdout`` and
        ``sys.stderr`` (see :mod:`tractusx_testlab.logging.transcript`), so a
        second handler here would copy these lines into it twice while still
        missing everything that does not come through this logger — the compile
        narration, the result banner, and the tracebacks, which is what made a
        per-logger file the wrong mechanism in the first place.
        """
        return StructuredLogger(
            name=f"{self._logger.name}.{job_id}",
            stream=None,
            level=self._logger.level,
        )

    def _log(self, level: int, msg: str, **kw: object) -> None:
        record = self._logger.makeRecord(self._logger.name, level, "(testlab)", 0, msg, (), None)
        if kw:
            record.extra_data = kw
        self._logger.handle(record)

    def debug(self, msg: str, **kw: object) -> None:
        self._log(logging.DEBUG, msg, **kw)

    def info(self, msg: str, **kw: object) -> None:
        self._log(logging.INFO, msg, **kw)

    def warning(self, msg: str, **kw: object) -> None:
        self._log(logging.WARNING, msg, **kw)

    def error(self, msg: str, **kw: object) -> None:
        self._log(logging.ERROR, msg, **kw)

    def close(self) -> None:
        """Flush and close the file handler if any."""
        if self._file_handler:
            self._file_handler.close()
            self._logger.removeHandler(self._file_handler)
            self._file_handler = None

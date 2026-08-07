#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""JSON-lines structured logger for test execution output."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Optional


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            entry["data"] = record.extra_data
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry, default=str, separators=(",", ":"))


class StructuredLogger:
    """Provides JSON-lines logging to a file and/or stream.

    Log files are organised by date and named after the job ID::

        <logs_dir>/2026-03-30/<job_id>.jsonl

    Usage::

        log = StructuredLogger("testlab.player", logs_dir=Path("~/.testlab/logs"))
        job_log = log.for_job("abc123")  # creates dated sub-dir + file
        job_log.info("Step started", step_index=0, step_type="create_asset")
    """

    __slots__ = ("_logger", "_file_handler", "_logs_dir")

    def __init__(
        self,
        name: str = "testlab",
        logs_dir: Optional[Path] = None,
        log_file: Optional[Path] = None,
        stream: Optional[IO] = None,
        level: int = logging.DEBUG,
    ) -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.propagate = False
        self._file_handler: Optional[logging.FileHandler] = None
        self._logs_dir = logs_dir

        # Always enable console output stream
        self._logger.addHandler(CliHandler(stream or sys.stdout))

        json_formatter = _JsonFormatter()

        # Explicit file handler (optional, for backward compat)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setFormatter(json_formatter)
            self._logger.addHandler(file_handler)
            self._file_handler = file_handler

    def for_job(self, job_id: str) -> "StructuredLogger":
        """Create a child logger that writes to ``<logs_dir>/<date>/<time>_<job_id>.jsonl``.

        The date directory is derived from the current UTC date.
        The file name is prefixed with the current UTC time (HH-MM-SS-fff)
        so that execution runs are ordered chronologically.
        """
        log_file: Optional[Path] = None
        if self._logs_dir:
            now = datetime.now(timezone.utc)
            date_dir = self._logs_dir / now.strftime("%Y-%m-%d")
            time_prefix = now.strftime("%H-%M-%S-") + f"{now.microsecond // 1000:03d}"
            log_file = date_dir / f"{time_prefix}_{job_id}.jsonl"

        return StructuredLogger(
            name=f"{self._logger.name}.{job_id}",
            log_file=log_file,
            stream=None,
            level=self._logger.level,
        )

    def _log(self, level: int, msg: str, **kw: object) -> None:
        record = self._logger.makeRecord(
            self._logger.name, level, "(testlab)", 0, msg, (), None
        )
        if kw:
            record.extra_data = kw  # type: ignore[attr-defined]
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

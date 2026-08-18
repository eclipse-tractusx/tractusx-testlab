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

"""JSON-lines structured logger for test execution output."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import IO


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            entry["data"] = record.extra_data
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry, default=str, separators=(",", ":"))


class CliHandler(logging.StreamHandler):
    """StreamHandler that formats structuredLogger records as human-readable text.
    Attach to any logger like a normal handler::

        handler = CliHandler()          # writes to stdout
        handler = CliHandler(sys.stderr)
        logger.addHandler(handler)
    """

    # Fallback used when no root console formatter is configured yet.
    _FALLBACK_FMT = "%(asctime)s [%(levelname)-8s] [%(name)-15s] %(message)s"
    _FALLBACK_DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, stream: IO = sys.stdout) -> None:
        super().__init__(stream)
        # Inherit the engine's console formatter so logging.yml changes apply here too.
        delegate = self._root_console_formatter()
        if delegate is not None:
            self.setFormatter(logging.Formatter(fmt=delegate._fmt, datefmt=delegate.datefmt))
        else:
            self.setFormatter(logging.Formatter(fmt=self._FALLBACK_FMT, datefmt=self._FALLBACK_DATEFMT))

    @staticmethod
    def _root_console_formatter() -> logging.Formatter | None:
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and handler.formatter is not None:
                return handler.formatter
        return None

    @classmethod
    def _build_inline_message(cls, base_msg: str, extra_data: dict[str, object]) -> str:
        parts: list[str] = [base_msg]

        # Add extra_data fields
        if "tck" in extra_data:
            parts.append(f"[{extra_data['tck']}]")
        if "script" in extra_data:
            parts.append(f"[{extra_data['script']}]")
        if "step_type" in extra_data:
            parts.append(f"[{extra_data['step_type']}]")
        if "phase" in extra_data:
            parts.append(f"[{extra_data['phase']}]")
        if "status" in extra_data:
            parts.append(f"[{extra_data['status']}]")
        if "duration_s" in extra_data:
            parts.append(f"[{extra_data['duration_s']}s]")
        if "request" in extra_data:
            parts.append(f"request:[{json.dumps(extra_data['request'], default=str)}]")
        if "response" in extra_data:
            parts.append(f"response:[{json.dumps(extra_data['response'], default=str)}]")
        if "error" in extra_data:
            parts.append(f"error:[{extra_data['error']}]")

        return " ".join(parts)

    def emit(self, record: logging.LogRecord) -> None:
        if hasattr(record, "extra_data") or (record.exc_info and record.exc_info[1]):
            record = logging.makeLogRecord(record.__dict__)
            if hasattr(record, "extra_data"):
                extra_data = dict(record.extra_data)
                record.msg = self._build_inline_message(record.getMessage(), extra_data)

                record.args = None
            if record.exc_info and record.exc_info[1]:
                record.msg = record.getMessage() + f" exception:[{record.exc_info[1]}]"
                record.args = None
                record.exc_info = None
        super().emit(record)


class StructuredLogger:
    """Provides JSON-lines logging to a file and/or stream.

    Log files are organised by date and named after the job ID::

        <logs_dir>/2026-03-30/<job_id>.jsonl

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

        json_formatter = _JsonFormatter()

        # Explicit file handler (optional, for backward compat)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setFormatter(json_formatter)
            self._logger.addHandler(file_handler)
            self._file_handler = file_handler

    def for_job(self, job_id: str) -> StructuredLogger:
        """Create a child logger that writes to ``<logs_dir>/<date>/<time>_<job_id>.jsonl``.

        The date directory is derived from the current UTC date.
        The file name is prefixed with the current UTC time (HH-MM-SS-fff)
        so that execution runs are ordered chronologically.
        """
        log_file: Path | None = None
        if self._logs_dir:
            now = datetime.now(UTC)
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

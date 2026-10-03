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

"""A run's transcript, trace and log file are for the account that ran it.

They carry what the run saw on the wire. Created under a umask of ``0``, so a
file that is ``0600`` was given that mode when it was created.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from tractusx_testlab.logging import transcript
from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.logging.trace import ExecutionTrace


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture(autouse=True)
def _permissive_umask() -> Iterator[None]:
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


def test_the_transcript_is_0600_in_0700_directories(tmp_path: Path) -> None:
    path = transcript.transcript_path(tmp_path / "logs", "run-a")

    with transcript.recording(path):
        print("a line the run printed")

    assert "a line the run printed" in path.read_text()
    assert _mode(path) == 0o600
    assert _mode(path.parent) == 0o700
    assert _mode(tmp_path / "logs") == 0o700


def test_the_execution_trace_is_0600_in_0700_directories(tmp_path: Path) -> None:
    trace = ExecutionTrace.for_job("tck", "run-a", tmp_path / "data")
    trace.close()

    assert trace.path is not None
    assert _mode(trace.path) == 0o600
    assert _mode(trace.path.parent) == 0o700
    assert _mode(tmp_path / "data") == 0o700


def test_a_log_file_is_0600(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "testlab.log"

    logger = StructuredLogger("testlab.private-records", log_file=log_file)
    logger.info("tck.started")
    logger.close()

    assert _mode(log_file) == 0o600
    assert _mode(log_file.parent) == 0o700

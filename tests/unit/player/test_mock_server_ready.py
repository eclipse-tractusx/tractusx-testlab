###############################################################
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
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.
"""The background mock server is listening once start() returns."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution import mock_server


class _SlowServer:
    """A uvicorn.Server double that starts listening after a few polls."""

    def __init__(self, config: object) -> None:
        self._polls = 0

    @property
    def started(self) -> bool:
        self._polls += 1
        return self._polls > 3

    def run(self) -> None:  # pragma: no cover - the thread double never runs it
        pass


def _patched(monkeypatch: pytest.MonkeyPatch, server: type, alive: bool = True) -> None:
    import tractusx_testlab.server.app as app_module

    monkeypatch.setattr(app_module, "create_app", MagicMock())
    uvicorn = MagicMock()
    uvicorn.Server = server
    monkeypatch.setattr(mock_server, "uvicorn", uvicorn)
    thread = MagicMock()
    thread.return_value.is_alive.return_value = alive
    monkeypatch.setattr(mock_server.threading, "Thread", thread)
    monkeypatch.setattr(mock_server, "_READY_POLL_S", 0)


def test_start_waits_until_the_server_listens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patched(monkeypatch, _SlowServer)
    server = mock_server._BackgroundMockServer(
        8100, TestlabConfig(storage_dir=tmp_path / "store", logs_dir=tmp_path / "logs")
    )
    server.start()
    assert server._server.started  # type: ignore[union-attr]


def test_a_server_that_dies_does_not_hold_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class _Never(_SlowServer):
        @property
        def started(self) -> bool:
            return False

    _patched(monkeypatch, _Never, alive=False)
    mock_server._BackgroundMockServer(
        8100, TestlabConfig(storage_dir=tmp_path / "store", logs_dir=tmp_path / "logs")
    ).start()
    assert "not listening yet" in caplog.text

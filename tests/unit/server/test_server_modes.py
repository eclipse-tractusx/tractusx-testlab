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

"""A server that answers a run's mocks offers nothing else.

The server a run publishes is reached by whoever the run hands an address to —
the system under test, or anyone who reads the address on its way there. With
the full API mounted, such a caller could post a YAML TCK and have the server
make requests on its behalf, name any ``.tck`` on the server's disk to run, or
upload, list and delete packages. In ``mock`` mode none of that is there; the
mocks, the callback route and the health check are.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution import mock_server
from tractusx_testlab.server import app as app_module
from tractusx_testlab.server.app import create_app
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import (
    MockResponse,
    clear_callback_manager,
    clear_mocks,
    register_mock,
    set_callback_manager,
)

_TCK_YAML = b"""\
syntax: v1-alpha
kind: tck
id: outsider
metadata: {name: Outsider, version: "1.0", authors: [], copyright_holders: [], license: x}
tests: []
"""

#: Every route that starts, reads or stops a run, or touches the package store.
_CONTROL_CALLS: list[tuple[str, str, dict[str, Any]]] = [
    ("POST", "/testlab/tck-execution/run", {"content": _TCK_YAML}),
    ("POST", "/testlab/run/yaml", {"content": _TCK_YAML}),
    ("POST", "/testlab/run/package", {"json": {"path": "/etc/passwd.tck"}}),
    ("POST", "/testlab/packages", {"files": {"file": ("x-1.0.tck", b"x")}}),
    ("GET", "/testlab/packages", {}),
    ("DELETE", "/testlab/packages/0123456789ab", {}),
    ("GET", "/testlab/tck-execution", {}),
    ("POST", "/testlab/compile", {"content": _TCK_YAML}),
    ("GET", "/openapi.json", {}),
    ("GET", "/docs", {}),
]


@pytest.fixture(autouse=True)
def _manager() -> Iterator[None]:
    set_callback_manager(CallbackManager())
    yield
    clear_mocks()
    clear_callback_manager()


def _config(tmp_path: Path, **overrides: Any) -> TestlabConfig:
    return TestlabConfig(storage_dir=tmp_path / "store", logs_dir=tmp_path / "logs", **overrides)


def _client(tmp_path: Path, **kwargs: Any) -> TestClient:
    config = kwargs.pop("config", None) or _config(tmp_path)
    return TestClient(create_app(config, **kwargs), raise_server_exceptions=False)


class TestTheMockOnlyServer:
    @pytest.mark.parametrize(("method", "path", "body"), _CONTROL_CALLS)
    def test_offers_no_control_route(
        self, tmp_path: Path, method: str, path: str, body: dict[str, Any]
    ) -> None:
        client = _client(tmp_path, mode="mock")

        answer = client.request(method, path, **body)

        assert answer.status_code == 404
        assert not hasattr(client.app.state, "player")

    def test_creates_no_package_store(self, tmp_path: Path) -> None:
        _client(tmp_path, mode="mock")

        assert not (tmp_path / "store").exists()

    def test_answers_a_runs_mock_and_its_callback_route(self, tmp_path: Path) -> None:
        client = _client(tmp_path, mode="mock")
        register_mock("/push", "POST", MockResponse(200, {"ok": True}), run="run-a")
        register_mock("/callbacks/ack", "POST", MockResponse(200, {"ack": True}), run="run-a")

        assert client.post("/runs/run-a/push", json={}).json() == {"ok": True}
        assert client.post("/testlab/callbacks/ack", json={}).json() == {"ack": True}
        assert client.get("/testlab/health").json()["status"] == "ok"

    def test_is_what_the_config_asks_for(self, tmp_path: Path) -> None:
        client = _client(tmp_path, config=_config(tmp_path, server_mode="mock"))

        assert client.get("/testlab/tck-execution").status_code == 404

    def test_an_explicit_mode_wins_over_the_config(self, tmp_path: Path) -> None:
        client = _client(tmp_path, config=_config(tmp_path, server_mode="mock"), mode="full")

        assert client.get("/testlab/tck-execution").status_code == 200


class TestTheFullServer:
    """``testlab serve``: unchanged, the whole API."""

    def test_is_the_default(self, tmp_path: Path) -> None:
        client = _client(tmp_path)

        assert client.get("/testlab/tck-execution").status_code == 200
        assert client.get("/testlab/packages").status_code == 200
        assert hasattr(client.app.state, "player")

    def test_still_answers_mocks(self, tmp_path: Path) -> None:
        client = _client(tmp_path)
        register_mock("/push", "POST", MockResponse(200, {"ok": True}))

        assert client.post("/push", json={}).json() == {"ok": True}


class TestTheServerAPlayerStartsForARun:
    @pytest.fixture()
    def built(self, monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
        """The mode each app the background server built was asked for; nothing listens."""
        modes: list[str | None] = []

        def spy(config: TestlabConfig, *, mode: str | None = None) -> MagicMock:
            modes.append(mode)
            return MagicMock()

        monkeypatch.setattr(app_module, "create_app", spy)
        monkeypatch.setattr(mock_server, "uvicorn", MagicMock())
        monkeypatch.setattr(mock_server.threading, "Thread", MagicMock())
        return modes

    def test_serves_the_runs_mocks_only(self, tmp_path: Path, built: list[str | None]) -> None:
        mock_server._BackgroundMockServer(8100, _config(tmp_path)).start()

        assert built == ["mock"]

    def test_serves_the_full_api_only_when_the_config_says_so(
        self, tmp_path: Path, built: list[str | None]
    ) -> None:
        mock_server._BackgroundMockServer(8100, _config(tmp_path, server_mode="full")).start()

        assert built == ["full"]

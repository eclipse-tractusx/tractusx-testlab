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

"""Integration tests for the FastAPI mock server (app creation + health)."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from tests.paths import SRC_DIR

_SRC_DIR = str(SRC_DIR)


@pytest.fixture()
def mock_app(tmp_path: Path) -> Generator[FastAPI, None, None]:
    """Create a FastAPI app with SDK dependencies mocked out."""
    path_inserted = _SRC_DIR not in sys.path
    if path_inserted:
        sys.path.insert(0, _SRC_DIR)

    mock_modules: dict[str, MagicMock] = {}
    modules_to_mock = [
        "tractusx_sdk.extensions.testlab.server.mock_registry",
        "tractusx_sdk.extensions.testlab.server.routes",
        "tractusx_sdk.extensions.testlab.server.callbacks",
        "tractusx_sdk.extensions.testlab.server.storage",
        "tractusx_sdk.extensions.testlab.player.execution.player",
        "tractusx_sdk.extensions.testlab.config.loader",
        "tractusx_sdk.extensions.testlab.config.settings",
    ]

    for mod_name in modules_to_mock:
        if mod_name not in sys.modules:
            mock_modules[mod_name] = MagicMock()
            sys.modules[mod_name] = mock_modules[mod_name]

    routes_mod = sys.modules["tractusx_sdk.extensions.testlab.server.routes"]
    routes_mod.router = APIRouter()

    evicted: dict[str, object] = {}
    for key in list(sys.modules.keys()):
        if "tractusx_testlab" in key:
            evicted[key] = sys.modules.pop(key)

    try:
        import tractusx_testlab.server.app as app_module

        importlib.reload(app_module)

        mock_config = MagicMock()
        mock_config.storage_dir = tmp_path / "testlab-mock-test"
        application = app_module.create_app(config=mock_config)
        yield application
    finally:
        for key, mod in evicted.items():
            sys.modules[key] = mod
        for mod_name in list(mock_modules.keys()):
            sys.modules.pop(mod_name, None)
        if path_inserted:
            sys.path.remove(_SRC_DIR)


@pytest.fixture()
def client(mock_app: FastAPI) -> TestClient:
    """HTTP test client for the mock server."""
    return TestClient(mock_app)


class TestMockServerApp:
    """Tests for the FastAPI application creation and basic endpoints."""

    def test_app_is_fastapi_instance(self, mock_app: FastAPI) -> None:
        assert isinstance(mock_app, FastAPI)

    def test_app_has_title(self, mock_app: FastAPI) -> None:
        assert mock_app.title == "Tractus-X Testlab Player"

    def test_health_endpoint_returns_200(self, client: TestClient) -> None:
        response = client.get("/testlab/health")
        assert response.status_code == 200

    def test_health_endpoint_json_has_status(self, client: TestClient) -> None:
        body = client.get("/testlab/health").json()
        assert "status" in body
        assert body["status"] == "ok"

    def test_app_state_has_player(self, mock_app: FastAPI) -> None:
        assert hasattr(mock_app.state, "player")

    def test_app_state_has_callbacks(self, mock_app: FastAPI) -> None:
        assert hasattr(mock_app.state, "callbacks")

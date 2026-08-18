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

"""Tests for the GET /testlab/health endpoint in the FastAPI application."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from tests.paths import SRC_DIR

# ---------------------------------------------------------------------------
# Fixture: build a FastAPI app from the *local* source with SDK deps mocked
# ---------------------------------------------------------------------------

_SRC_DIR = str(SRC_DIR)


@pytest.fixture()
def app() -> Generator[FastAPI, None, None]:
    """Create a FastAPI app with SDK dependencies mocked out.

    Inserts the local ``src/`` directory at the front of sys.path so that
    the worktree version of the server module is imported (not whatever is
    installed globally).
    """
    # Ensure local src is importable with highest priority
    path_inserted = _SRC_DIR not in sys.path
    if path_inserted:
        sys.path.insert(0, _SRC_DIR)

    # Mock SDK submodules that may not exist in the installed SDK version
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

    # Ensure routes mock provides a real APIRouter (so include_router works)
    routes_mod = sys.modules["tractusx_sdk.extensions.testlab.server.routes"]
    routes_mod.router = APIRouter()

    # Evict any cached copy so we reload from the local source
    evicted: dict[str, object] = {}
    for key in list(sys.modules.keys()):
        if "tractusx_testlab" in key:
            evicted[key] = sys.modules.pop(key)

    try:
        import tractusx_testlab.server.app as app_module

        importlib.reload(app_module)

        mock_config = MagicMock()
        mock_config.storage_dir = "/tmp/testlab-health-test"
        application = app_module.create_app(config=mock_config)
        yield application
    finally:
        # Restore module state
        for key, mod in evicted.items():
            sys.modules[key] = mod
        for mod_name in list(mock_modules.keys()):
            sys.modules.pop(mod_name, None)
        if path_inserted:
            sys.path.remove(_SRC_DIR)


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """HTTP test client for the application."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /testlab/health — connectivity validation endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        # Act
        response = client.get("/testlab/health")

        # Assert
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_health_response_contains_status_ok(self, client: TestClient) -> None:
        # Act
        body = client.get("/testlab/health").json()

        # Assert
        assert "status" in body, "Response missing 'status' field"
        assert body["status"] == "ok", f"Expected status 'ok', got '{body['status']}'"

    def test_health_response_contains_version(self, client: TestClient) -> None:
        # Act
        body = client.get("/testlab/health").json()

        # Assert
        assert "version" in body, "Response missing 'version' field"

    def test_health_version_is_nonempty_string(self, client: TestClient) -> None:
        # Act
        body = client.get("/testlab/health").json()

        # Assert
        version = body["version"]
        assert isinstance(version, str), f"Version should be str, got {type(version)}"
        assert len(version) > 0, "Version string must not be empty"

    def test_health_version_matches_package_metadata(self, client: TestClient) -> None:
        """Version returned must match importlib.metadata for the package."""
        import importlib.metadata

        # Arrange
        expected_version = importlib.metadata.version("tractusx-testlab")

        # Act
        body = client.get("/testlab/health").json()

        # Assert
        assert body["version"] == expected_version, (
            f"Expected version '{expected_version}', got '{body['version']}'"
        )

    def test_health_response_has_exactly_two_keys(self, client: TestClient) -> None:
        """Endpoint should not leak extra fields."""
        # Act
        body = client.get("/testlab/health").json()

        # Assert
        assert set(body.keys()) == {"status", "version"}, (
            f"Unexpected keys in response: {set(body.keys())}"
        )

    def test_health_response_content_type_is_json(self, client: TestClient) -> None:
        # Act
        response = client.get("/testlab/health")

        # Assert
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected JSON content-type, got '{content_type}'"
        )

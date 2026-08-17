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

"""Tests for the POST /testlab/compile endpoint."""

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
# Fixture: build a FastAPI app from local source with SDK deps mocked
# ---------------------------------------------------------------------------

_SRC_DIR = str(SRC_DIR)


@pytest.fixture()
def app() -> Generator[FastAPI, None, None]:
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
        mock_config.storage_dir = "/tmp/testlab-compile-test"
        yield app_module.create_app(config=mock_config)
    finally:
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
# Minimal valid YAML for a test script
# ---------------------------------------------------------------------------

_VALID_YAML = """\
syntax: v1-alpha
kind: test
id: smoke-check
namespace: testlab.smoke
metadata:
  name: smoke-check
  version: "1.0"
execution: []
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompileYamlEndpoint:
    """Tests for POST /testlab/compile — YAML compile/validate."""

    def test_compile_valid_yaml_returns_ok(self, client: TestClient) -> None:
        """Valid test YAML compiles without errors."""
        # Act
        response = client.post(
            "/testlab/compile",
            content=_VALID_YAML.encode(),
        )

        # Assert
        body = response.json()
        assert body["status"] == "ok", f"Expected status 'ok', got {body['status']!r}"
        assert body["errors"] == [], f"Expected no errors, got {body['errors']}"

    def test_compile_empty_body_returns_error(self, client: TestClient) -> None:
        """An empty request body produces an error about the missing body."""
        # Act
        response = client.post(
            "/testlab/compile",
            content=b"",
        )

        # Assert
        body = response.json()
        assert body["status"] == "error", f"Expected status 'error', got {body['status']!r}"
        assert any(
            "empty" in err["message"].lower() for err in body["errors"]
        ), f"Expected an error mentioning 'empty', got {body['errors']}"

    def test_compile_malformed_yaml_returns_error(self, client: TestClient) -> None:
        """Unparseable YAML produces a syntax error."""
        # Act
        response = client.post(
            "/testlab/compile",
            content=b"{{invalid",
        )

        # Assert
        body = response.json()
        assert body["status"] == "error", f"Expected status 'error', got {body['status']!r}"
        assert any(
            "yaml" in err["message"].lower() or "syntax" in err["message"].lower()
            for err in body["errors"]
        ), f"Expected YAML syntax error, got {body['errors']}"

    def test_compile_unknown_kind_returns_error(self, client: TestClient) -> None:
        """An unrecognised ``kind`` value produces a structured error."""
        # Arrange
        yaml_body = b"kind: unknown_thing\nname: bad\nversion: '1.0'\n"

        # Act
        response = client.post(
            "/testlab/compile",
            content=yaml_body,
        )

        # Assert
        body = response.json()
        assert body["status"] == "error", f"Expected status 'error', got {body['status']!r}"
        assert any(
            "unknown" in err["message"].lower() and "kind" in err["path"].lower()
            for err in body["errors"]
        ), f"Expected unknown-kind error at path 'kind', got {body['errors']}"

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param(_VALID_YAML.encode(), id="valid-yaml"),
            pytest.param(b"", id="empty-body"),
            pytest.param(b"{{invalid", id="malformed-yaml"),
            pytest.param(b"kind: unknown_thing\n", id="unknown-kind"),
        ],
    )
    def test_compile_always_returns_200(
        self, client: TestClient, content: bytes
    ) -> None:
        """The compile endpoint always returns HTTP 200 — errors are application-level."""
        # Act
        response = client.post("/testlab/compile", content=content)

        # Assert
        assert response.status_code == 200, (
            f"Expected HTTP 200, got {response.status_code}"
        )

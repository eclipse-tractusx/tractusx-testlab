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

"""FastAPI application factory for the Testlab server."""

from __future__ import annotations

import importlib.metadata
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import (
    get_callback_manager,
    resolve_mock,
    set_callback_manager,
)
from tractusx_testlab.server.routes import router
from tractusx_testlab.server.storage import PackageStorage

_logger = logging.getLogger(__name__)


def create_app(config: TestlabConfig | None = None) -> FastAPI:
    """Build and return a fully-wired FastAPI application.

    Args:
        config: Optional pre-loaded configuration. Defaults to ``ConfigLoader.load()``.
    """
    if config is None:
        config = ConfigLoader.load()

    app = FastAPI(
        title="Tractus-X Testlab Player",
        version="0.7.1",
        description="Automated test execution for Tractus-X dataspace interoperability.",
    )

    # Shared instances — stored on app.state for FastAPI dependency injection
    app.state.player = TestlabPlayer(config=config)
    app.state.storage = PackageStorage(base_dir=Path(config.storage_dir) / "packages")
    existing_manager = get_callback_manager()
    app.state.callbacks = existing_manager if existing_manager is not None else CallbackManager()
    set_callback_manager(app.state.callbacks)

    app.include_router(router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/testlab/health", tags=["testlab"])
    async def health() -> JSONResponse:
        """Lightweight health check for IDE connectivity validation."""
        try:
            version = importlib.metadata.version("tractusx-testlab")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        return JSONResponse(content={"status": "ok", "version": version})

    # ── Catch-all for mock endpoints registered at arbitrary paths ─────
    # SUTs send callbacks to URLs like /companycertificate/status.
    # This route must be added LAST so it doesn't shadow named routes.
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def mock_catch_all(path: str, request: Request) -> JSONResponse:
        """Handle inbound calls to dynamically-registered mock endpoints."""
        full_path = f"/{path}"
        method = request.method
        headers = dict(request.headers)
        body = None
        if method in ("POST", "PUT"):
            try:
                body = await request.json()
            except ValueError:
                body = {}

        callbacks: CallbackManager = app.state.callbacks
        mock = resolve_mock(
            full_path, method,
            headers=headers, query_params=dict(request.query_params), body=body,
        )

        # A path no step opened is refused. `resolve` buffers a call nothing is
        # waiting for and reports success for it — right when the SUT beats the
        # script to its own wait step, wrong for an address that was never
        # registered: the SUT is told 200 for a call that reached nobody, and
        # the script then waits out its timeout on the address it did open.
        if mock is None and not callbacks.has_listener(full_path, method):
            raise HTTPException(404, f"No mock or listener for {method} {full_path}")

        # Resolve the callback listener (so wait_for_call steps unblock)
        matched = callbacks.resolve(
            full_path, method, headers, body, dict(request.query_params)
        )
        if mock is not None:
            _safe_path = full_path[:80].replace("\n", "").replace("\r", "")
            _logger.debug("Mock catch-all matched %s %s -> %d", method, _safe_path, mock.status_code)
            return JSONResponse(
                content=mock.body, status_code=mock.status_code, headers=mock.headers or None
            )
        if matched:
            return JSONResponse(content={"status": "received"})

        raise HTTPException(404, f"No mock or listener for {method} {full_path}")

    return app

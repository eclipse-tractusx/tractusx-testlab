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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""FastAPI application factory for the Testlab server.

Two shapes of one app (``ServerMode``). ``full`` is ``testlab serve``: the
package, compile and job API, live events, and the mocks and callbacks of the
runs it starts. ``mock`` is what a run needs while it is going and nothing
more — the mock and callback routes the system under test calls — for a
server that is reachable by whoever a run hands an address to: the one the
player starts for a run, or one an engine starts and forwards calls to. Such a
server must not take a package path or a YAML body from that caller and run it.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import get_callback_manager, set_callback_manager
from tractusx_testlab.server.routes import inbound_router, router
from tractusx_testlab.server.routes.callbacks import answer
from tractusx_testlab.server.storage import PackageStorage

#: Which routes a server mounts — see the module docstring.
ServerMode = Literal["full", "mock"]


def _version() -> str:
    """The installed package version — the one source of it.

    Three numbers used to be in play: ``pyproject`` said one thing, this file
    hardcoded ``0.7.1`` into the OpenAPI document, and ``/testlab/health``
    reported a third from the package metadata. An IDE checking compatibility
    against the health endpoint and a reader of the API docs saw different
    versions of the same server.
    """
    try:
        return importlib.metadata.version("tractusx-testlab")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def create_app(config: TestlabConfig | None = None, *, mode: ServerMode | None = None) -> FastAPI:
    """Build and return a fully-wired FastAPI application.

    Args:
        config: Optional pre-loaded configuration. Defaults to ``ConfigLoader.load()``.
        mode: ``full`` or ``mock`` (``ServerMode``). Unset, ``config.server_mode``
            decides, and ``full`` when that is unset too — what ``testlab serve``
            has always served. An embedding host that only needs a run's mocks
            answered passes ``mock``.
    """
    if config is None:
        config = ConfigLoader.load()
    is_mock_only = (mode or getattr(config, "server_mode", None)) == "mock"

    app = FastAPI(
        title="Tractus-X Testlab Player",
        version=_version(),
        description="Automated TCK execution for Tractus-X dataspace interoperability.",
        openapi_url=None if is_mock_only else "/openapi.json",
        docs_url=None if is_mock_only else "/docs",
        redoc_url=None if is_mock_only else "/redoc",
    )

    # Shared instances — stored on app.state for FastAPI dependency injection
    existing_manager = get_callback_manager()
    app.state.callbacks = existing_manager if existing_manager is not None else CallbackManager()
    set_callback_manager(app.state.callbacks)
    if is_mock_only:
        app.include_router(inbound_router)
    else:
        _mount_control_api(app, config)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/testlab/health", tags=["testlab"])
    async def health() -> JSONResponse:
        """Lightweight health check for IDE connectivity validation."""
        return JSONResponse(content={"status": "ok", "version": _version()})

    # ── Catch-all for mock endpoints registered at arbitrary paths ─────
    # SUTs send callbacks to URLs like /companycertificate/status, or to the
    # run's own address /runs/<run>/companycertificate/status. This route must
    # be added LAST so it doesn't shadow named routes.
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def mock_catch_all(path: str, request: Request) -> JSONResponse:
        """Handle inbound calls to dynamically-registered mock endpoints."""
        return await answer(request, f"/{path}")

    return app


def _mount_control_api(app: FastAPI, config: TestlabConfig) -> None:
    """Give *app* the player, the package store and the routes that drive them."""
    app.state.player = TestlabPlayer(config=config)
    app.state.storage = PackageStorage(base_dir=Path(config.storage_dir) / "packages")
    app.include_router(router)

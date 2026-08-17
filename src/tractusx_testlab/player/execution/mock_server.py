#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Background mock server for CLI execution — starts uvicorn in a daemon thread."""

from __future__ import annotations

import logging
import threading

import uvicorn

from tractusx_testlab.config.settings import TestlabConfig

logger = logging.getLogger(__name__)


class _BackgroundMockServer:
    """Starts the TestLab mock server in a background daemon thread.

    Used by ``TestlabPlayer`` when running via CLI (no external server).
    The server handles mock endpoint responses and callback listeners.
    """

    __slots__ = ("_config", "_port", "_server", "_thread")

    def __init__(self, port: int, config: TestlabConfig) -> None:
        self._port = port
        self._config = config
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None

    def start(self) -> None:
        """Start the mock server on a background daemon thread."""
        from tractusx_testlab.server.app import create_app

        app = create_app(config=self._config)
        uv_config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=self._port,
            log_level="warning",
        )
        self._server = uvicorn.Server(uv_config)

        self._thread = threading.Thread(
            target=self._server.run,
            name="testlab-mock-server",
            daemon=True,
        )
        self._thread.start()
        logger.info("Mock server started on port %d (background thread)", self._port)

    def stop(self) -> None:
        """Signal the server to shut down."""
        if self._server is not None:
            self._server.should_exit = True
            logger.info("Mock server shutdown requested")

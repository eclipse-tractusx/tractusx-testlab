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

"""Background mock server for CLI execution — starts uvicorn in a daemon thread."""

from __future__ import annotations

import logging
import threading
import time

import uvicorn

from tractusx_testlab.config.settings import TestlabConfig

logger = logging.getLogger(__name__)

#: How long ``start`` waits for the server to listen before carrying on regardless.
_READY_TIMEOUT_S = 10.0
_READY_POLL_S = 0.01


class _BackgroundMockServer:
    """Starts the TestLab mock server in a background daemon thread.

    Used by ``TestlabPlayer`` when running via CLI (no external server).
    The server handles mock endpoint responses and callback listeners — and,
    unless the config says ``server_mode: full``, nothing else: it listens on
    every interface for the system under test to call, and a caller of a
    run's mock has no business starting runs, uploading packages or reading
    jobs (``server.app``). Those routes would drive a player of their own, not
    the run this server was started for.
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

        app = create_app(
            config=self._config, mode="full" if self._config.server_mode == "full" else "mock"
        )
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
        self._await_listening()
        logger.info("Mock server started on port %d (background thread)", self._port)

    def _await_listening(self) -> None:
        """Return once the server listens, so the run's first call cannot beat it.

        The thread binds the socket some milliseconds after it starts. A step
        that calls one of the run's own mocks straight away — a discovery
        lookup against ``mock/discovery`` is one — was refused a connection
        while uvicorn was still starting. A server that never comes up is
        reported and the run goes on: a run that uses no mock does not need it.
        """
        deadline = time.monotonic() + _READY_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._server is None or self._server.started:
                return
            if self._thread is not None and not self._thread.is_alive():
                break
            time.sleep(_READY_POLL_S)
        logger.warning("Mock server on port %d is not listening yet", self._port)

    def stop(self) -> None:
        """Signal the server to shut down."""
        if self._server is not None:
            self._server.should_exit = True
            logger.info("Mock server shutdown requested")

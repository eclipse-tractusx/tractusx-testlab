################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""The TestLab mock server, started the way the CLI starts it.

``mock/api`` and ``mock/wait/http_request`` are the only pair of steps that do
not talk to each other through the run context: one registers a route on this
server and the other blocks on a listener the server resolves. Nothing about
that is visible from either step's contract, and neither step does anything at
all without the server running — so testing them means running it.

It is the real ``create_app`` on a real port in a background thread, which is
also what makes the interesting part testable: the request arrives on uvicorn's
event loop while the waiting future belongs to the test's.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

import requests

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution.mock_server import _BackgroundMockServer


def free_port() -> int:
    """A port nothing is listening on, so tests can run side by side."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class MockServer:
    """A running TestLab server, and a way to call it as the SUT would."""

    def __init__(self) -> None:
        self.port = free_port()
        self.config = TestlabConfig(server_port=self.port)
        self._server = _BackgroundMockServer(self.port, self.config)

    # -- lifecycle --------------------------------------------------------

    def start(self, timeout_s: float = 10.0) -> MockServer:
        """Start serving and block until the health endpoint answers."""
        self._server.start()
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                requests.get(self._health_url, timeout=0.5)
                return self
            except requests.RequestException:
                time.sleep(0.02)
        raise RuntimeError(f"Mock server did not come up on port {self.port}")

    def stop(self) -> None:
        self._server.stop()

    @property
    def _health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/testlab/health"

    # -- acting as the system under test ----------------------------------

    def local(self, url: str) -> str:
        """The URL a step handed out, as a client on this machine can reach it.

        ``mock/api`` publishes a ``localhost`` URL while the server binds
        ``0.0.0.0``; on a host where ``localhost`` resolves to IPv6 first, that
        difference is the whole test.
        """
        return url.replace("localhost", "127.0.0.1")

    def call(
        self,
        url: str,
        method: str = "POST",
        json: Any = None,
        params: dict | None = None,
        timeout: float = 5.0,
    ) -> requests.Response:
        """Call the mock, the way the system under test would."""
        return requests.request(
            method, self.local(url), json=json, params=params, timeout=timeout
        )

    def call_soon(self, url: str, delay_s: float = 0.2, **kwargs: Any) -> _LateCall:
        """Call the mock from another thread after *delay_s*.

        The point of these steps is that the call arrives while the script is
        already blocked, so the call has to come from somewhere other than the
        awaiting coroutine.
        """
        return _LateCall(self, url, delay_s, kwargs).start()


class _LateCall:
    """A call made from another thread, whose outcome the test can read back."""

    def __init__(
        self, server: MockServer, url: str, delay_s: float, kwargs: dict
    ) -> None:
        self._server = server
        self._url = url
        self._delay_s = delay_s
        self._kwargs = kwargs
        self._thread: threading.Thread | None = None
        self.response: requests.Response | None = None
        self.error: Exception | None = None

    def start(self) -> _LateCall:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        time.sleep(self._delay_s)
        try:
            self.response = self._server.call(self._url, **self._kwargs)
        except requests.RequestException as exc:
            self.error = exc

    def wait(self, timeout_s: float = 10.0) -> requests.Response:
        """The response the mock gave the caller."""
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
        if self.error is not None:
            raise self.error
        if self.response is None:
            raise AssertionError("The call never completed")
        return self.response

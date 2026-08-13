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

"""A real HTTP server for the steps that make real HTTP requests.

``http/http_request`` calls out through ``requests``. Patching that away would
test the patch, so these tests answer a socket instead: a stdlib server on a
loopback port, which is fast enough to start per test and real enough that the
request the step built is the request the server received.

A route may hold several responses. The first call gets the first, the second
the second, and the last one repeats — which is how a flaky endpoint is written
here, and the only honest way to test ``flow/retry``.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse


@dataclass
class Response:
    """What a route answers with."""

    status: int = 200
    body: Any = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ReceivedRequest:
    """What the server was actually sent."""

    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: Any


class HttpDouble:
    """A loopback HTTP server whose routes and traffic a test can inspect."""

    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], list[Response]] = {}
        self.received: list[ReceivedRequest] = []
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # -- setup ------------------------------------------------------------

    def route(
        self,
        method: str,
        path: str,
        *responses: Response,
    ) -> "HttpDouble":
        """Answer *method* *path* with *responses*, the last one repeating."""
        if not responses:
            raise ValueError("A route needs at least one response.")
        self._routes[(method.upper(), path)] = list(responses)
        return self

    def json_route(
        self, method: str, path: str, body: Any, status: int = 200
    ) -> "HttpDouble":
        """The common case — one JSON response, every time."""
        return self.route(method, path, Response(status=status, body=body))

    # -- lifecycle --------------------------------------------------------

    def start(self) -> str:
        """Start serving and return the base URL."""
        double = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args: Any) -> None:
                """Keep the pytest output about the tests."""

            def _handle(self) -> None:
                parsed = urlparse(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw) if raw else None
                except json.JSONDecodeError:
                    body = raw.decode("utf-8", "replace")

                double.received.append(
                    ReceivedRequest(
                        method=self.command,
                        path=parsed.path,
                        query=parse_qs(parsed.query),
                        headers=dict(self.headers),
                        body=body,
                    )
                )

                response = double._next_response(self.command, parsed.path)
                payload = json.dumps(response.body).encode("utf-8")
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                for name, value in response.headers.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(payload)

            do_GET = _handle
            do_POST = _handle
            do_PUT = _handle
            do_PATCH = _handle
            do_DELETE = _handle

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        """Stop serving; safe to call when never started."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    # -- inspection -------------------------------------------------------

    def _next_response(self, method: str, path: str) -> Response:
        """The response this call gets, advancing a multi-response route."""
        queued = self._routes.get((method, path))
        if queued is None:
            return Response(
                status=404,
                body={"error": f"No route for {method} {path}", "known": self.known()},
            )
        return queued.pop(0) if len(queued) > 1 else queued[0]

    def known(self) -> list[str]:
        """Every route registered, for a 404 that says what was expected."""
        return [f"{method} {path}" for method, path in sorted(self._routes)]

    def calls_to(self, method: str, path: str) -> list[ReceivedRequest]:
        """Every request that reached *method* *path*."""
        return [
            request
            for request in self.received
            if request.method == method.upper() and request.path == path
        ]

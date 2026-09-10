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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""A stand-in system under test that calls back later, from its own process.

``mock/wait/http_request`` exists for the moment a script has nothing left to
do but wait: it handed the SUT an address, and the SUT will call it when it is
ready — not when the script is. Nothing in the dataspace this suite deploys
calls back on its own initiative, so this is the component that does. A
script tells it *what* to call and *how long* to wait, gets an acknowledgement
at once, and blocks on its wait step; the call then arrives while the script
is blocked, made by another process, from wherever this runs.

Standard library only, so it runs unchanged as a bare ``python:alpine`` pod in
the cluster and as a subprocess in the offline tests.

    POST /call   {"url": ..., "delay_s": 3, "method": "POST", "body": {...}}
                 -> 202 {"scheduled": true}, then the request after the delay
    GET  /health -> 200 {"status": "ok"}
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_DEFAULT_DELAY_S = 3.0


def _fire(url: str, method: str, body: object, delay_s: float) -> None:
    """Sleep, then make the call the script asked for."""
    time.sleep(delay_s)
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method=method)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(f"called {method} {url} -> {response.status}", flush=True)
    except urllib.error.URLError as exc:
        print(f"calling {method} {url} failed: {exc}", file=sys.stderr, flush=True)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args, flush=True)

    def _answer(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._answer(200, {"status": "ok"})
            return
        self._answer(404, {"error": f"no route for GET {self.path}"})

    def do_POST(self) -> None:
        if self.path != "/call":
            self._answer(404, {"error": f"no route for POST {self.path}"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            order = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._answer(400, {"error": "body is not JSON"})
            return
        url = order.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            self._answer(400, {"error": "'url' must be an http(s) URL"})
            return
        delay_s = float(order.get("delay_s", _DEFAULT_DELAY_S))
        method = str(order.get("method", "POST")).upper()
        threading.Thread(
            target=_fire, args=(url, method, order.get("body"), delay_s), daemon=True
        ).start()
        self._answer(202, {"scheduled": True, "url": url, "delay_s": delay_s, "method": method})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"stub caller listening on {args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

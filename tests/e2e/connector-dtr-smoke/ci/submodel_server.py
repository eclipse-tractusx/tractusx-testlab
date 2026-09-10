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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The submodel payload store the Industry Core journey has nothing else to run against.

TestLab's ``digital-twin/submodel/upload`` and ``digital-twin/submodel/delete``
steps address the engine's own submodel server, bound as
``engine.dtr.submodel_base_url``. A shell descriptor in a Digital Twin Registry
is only a pointer: it says where a submodel's payload lives, and something else
has to actually serve that payload. The Umbrella profile this suite deploys
switches off both ``simple-data-backend`` bundles, so the dataspace has no such
server, and those two steps plus the whole Industry Core journey — upload a
submodel, register a descriptor pointing at it, negotiate the asset that fronts
it, and pull the payload back through two data planes — have nothing to run
against.

This is that server: a payload store with no opinion about what it holds,
reachable both from the engine (over its ingress) and from the provider's data
plane (over the same hostname, which the cluster's DNS resolves too), so one
address serves both roles.

Standard library only, so it runs unchanged as a bare ``python:alpine`` pod in
the cluster and as a subprocess in the offline tests.

    GET    /health  -> 200 {"status": "ok"}
    POST   /<path>  -> 201 with the stored document; stores the JSON body
    PUT    /<path>  -> 200 with the stored document; overwrites
    GET    /<path>  -> 200 with the stored document, or 404
    DELETE /<path>  -> 204 empty when it was there, 404 otherwise
"""

from __future__ import annotations

import argparse
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_STORE: dict[str, object] = {}
_LOCK = threading.Lock()
_INVALID = object()
_MISSING = object()


def _key(path: str) -> str:
    """Reduce a request path to the identity of the resource it names.

    The engine stores a submodel at ``<server>/<percent-encoded aspect URN>/
    <submodel id>``, and the same payload is later fetched by an EDC data plane
    that appended a path of its own to the asset's base URL. The two do not
    necessarily spell that path identically: one may percent-encode a character
    the other left alone. Resolving the percent-escapes and stripping the
    surrounding slashes makes ``%23`` and ``#`` the same resource rather than
    two. Any query string is dropped first, since a data plane may append one.
    """
    return urllib.parse.unquote(path.split("?", 1)[0]).strip("/")


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args, flush=True)

    def _answer(self, status: int, body: object) -> None:
        if body is None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_document(self) -> object:
        """Return the JSON body, or ``_INVALID`` when it does not parse."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return _INVALID

    def _store(self, status: int) -> None:
        document = self._read_document()
        if document is _INVALID:
            self._answer(400, {"error": "body is not JSON"})
            return
        key = _key(self.path)
        with _LOCK:
            _STORE[key] = document
        self._answer(status, document)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._answer(200, {"status": "ok"})
            return
        key = _key(self.path)
        with _LOCK:
            document = _STORE.get(key, _MISSING)
        if document is _MISSING:
            self._answer(404, {"error": f"no submodel stored at {key}"})
            return
        self._answer(200, document)

    def do_POST(self) -> None:
        self._store(201)

    def do_PUT(self) -> None:
        self._store(200)

    def do_DELETE(self) -> None:
        key = _key(self.path)
        with _LOCK:
            existed = _STORE.pop(key, _MISSING) is not _MISSING
        if not existed:
            self._answer(404, {"error": f"no submodel stored at {key}"})
            return
        self._answer(204, None)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"submodel server listening on {args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

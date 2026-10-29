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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Loading an API file: read once, checked once, shared by every reader.

:func:`load_api_document` is the one way an API file (``env.apis``, ADR-0030)
becomes data, for the compiler and the player alike. It reads at most
:data:`MAX_API_FILE_BYTES`, parses the bytes as the declared type
(:mod:`~tractusx_testlab.openapi.parsing`), requires OpenAPI 3.0.x or 3.1.x,
walks the document once for its size and its references
(:mod:`~tractusx_testlab.openapi.ref_walk`) and freezes it
(:mod:`~tractusx_testlab.openapi.readonly`). Nothing is fetched: there is no
network access and no file is opened but the one named.

A loaded document is cached by its resolved path and the SHA-256 of its bytes.
The validator, the IR builder and the player of one process share one parse;
an edited file has another digest, so it is parsed again rather than served
stale. The bytes are read and hashed on every call, which is what makes that
true, and costs a fraction of a parse.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tractusx_testlab.models.primitives.exceptions import AuthoringError
from tractusx_testlab.openapi.parsing import ParseError, parse
from tractusx_testlab.openapi.readonly import RecordedDocument, freeze
from tractusx_testlab.openapi.ref_walk import DocumentShapeError, reference_problems

#: Largest API file a TCK may carry: 5 MiB. The published Catena-X and partner
#: documents are well under 1 MiB (Industry Core Hub: 190 KiB, 54 operations);
#: the limit bounds what one package can make every engine parse.
MAX_API_FILE_BYTES = 5 * 1024 * 1024

#: The OpenAPI versions an API file may declare (ADR-0030).
SUPPORTED_VERSIONS = re.compile(r"^3\.[01]\.\d+(?:-[0-9A-Za-z.-]+)?$")

#: How many parsed documents a process keeps, and how many bytes of source
#: they may add up to: a parsed document takes several times its file size in
#: memory, and an engine process runs one package after another.
CACHE_SIZE = 16
CACHE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ApiDocument:
    """A loaded API file: its digest, its OpenAPI version and its content."""

    sha256: str
    openapi: str
    #: Size of the file it was read from, in bytes.
    size: int
    #: The document, read-only; what ``${{ env.apis.<id> }}`` resolves to. A
    #: record of the run shows its summary instead of its content.
    content: RecordedDocument


class ApiDocumentError(AuthoringError):
    """An API file the TCK may not carry; each problem completes "the file …"."""

    code = "API_DOCUMENT_INVALID"

    def __init__(self, problems: list[str]) -> None:
        self.problems = tuple(problems)
        self.diagnostics = {"problems": list(self.problems)}
        super().__init__("; ".join(self.problems))


_lock = threading.Lock()
_cache: OrderedDict[tuple[str, str], ApiDocument] = OrderedDict()
_cached_bytes = 0


def load_api_document(path: Path, media_type: str) -> ApiDocument:
    """The API file at *path*, read as *media_type*, checked and read-only.

    Raises:
        ApiDocumentError: listing every problem found, each a phrase that
            completes "the file …" (``is Swagger 2.0, …``).
    """
    data = _read(path)
    key = (str(path.resolve()), hashlib.sha256(data).hexdigest())
    with _lock:
        if (cached := _cache.get(key)) is not None:
            _cache.move_to_end(key)
            return cached
    document = _checked(data, media_type, key[1])
    _remember(key, document)
    return document


def _remember(key: tuple[str, str], document: ApiDocument) -> None:
    """Cache *document*, evicting the least recently used past either bound."""
    global _cached_bytes
    with _lock:
        if key in _cache:
            return
        _cache[key] = document
        _cached_bytes += document.size
        while len(_cache) > 1 and (len(_cache) > CACHE_SIZE or _cached_bytes > CACHE_BYTES):
            _cached_bytes -= _cache.popitem(last=False)[1].size


def forget_api_documents() -> None:
    """Drop every cached document. For tests; a process never needs to."""
    global _cached_bytes
    with _lock:
        _cache.clear()
        _cached_bytes = 0


def _read(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_API_FILE_BYTES + 1)
    except OSError as exc:
        raise ApiDocumentError([f"cannot be read: {exc.strerror or exc}"]) from None
    if len(data) > MAX_API_FILE_BYTES:
        raise ApiDocumentError(
            [f"is larger than {MAX_API_FILE_BYTES // (1024 * 1024)} MiB, the limit for an API file"]
        )
    return data


def _checked(data: bytes, media_type: str, digest: str) -> ApiDocument:
    try:
        value = parse(data, media_type)
    except ParseError as exc:
        raise ApiDocumentError([str(exc)]) from None
    if not isinstance(value, dict):
        raise ApiDocumentError(["is not an OpenAPI document: its top level is not a mapping"])
    if problems := _version_problems(value):
        raise ApiDocumentError(problems)
    try:
        problems = reference_problems(value)
    except DocumentShapeError as exc:
        raise ApiDocumentError([str(exc)]) from None
    if problems:
        raise ApiDocumentError(problems)
    info = value["info"]
    summary = {
        "api_document": {
            "openapi": value["openapi"],
            "title": info["title"],
            "version": info["version"],
            "sha256": digest,
        }
    }
    return ApiDocument(
        sha256=digest,
        openapi=value["openapi"],
        size=len(data),
        content=RecordedDocument(freeze(value), summary),
    )


def _version_problems(document: dict[str, Any]) -> list[str]:
    """Why *document* is not an OpenAPI 3.0.x / 3.1.x document, if it is not."""
    if "swagger" in document:
        return [
            f"is Swagger {document['swagger']}, which is not supported; convert it to "
            "OpenAPI 3.0 or 3.1 first (e.g. with swagger2openapi)"
        ]
    version = document.get("openapi")
    if version is None:
        return ["is not an OpenAPI document: it has no 'openapi' version"]
    if not isinstance(version, str):
        return [f"declares 'openapi: {version}' as a number; quote it, e.g. openapi: \"3.0.3\""]
    if not SUPPORTED_VERSIONS.match(version):
        return [f"is OpenAPI {version}; only 3.0.x and 3.1.x are supported"]
    problems: list[str] = []
    info = document.get("info")
    if not isinstance(info, dict):
        problems.append("has no 'info' object")
    else:
        problems += [
            f"has no 'info.{key}' text"
            for key in ("title", "version")
            if not isinstance(info.get(key), str)
        ]
    sections = ("paths",) if version.startswith("3.0.") else ("paths", "webhooks", "components")
    present = [name for name in sections if name in document]
    if not present:
        problems.append(f"has no {' or '.join(repr(name) for name in sections)}")
    problems += [
        f"has a '{name}' that is not a mapping"
        for name in present
        if not isinstance(document[name], dict)
    ]
    return problems

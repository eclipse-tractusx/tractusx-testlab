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

"""Where a request built from an API document may go.

The test names the base URL. The document's first ``servers`` URL is a default
only when it is a literal, absolute http(s) URL; its path names the base path
a data plane call strips. Nothing else in the document — per-operation
``servers``, templated hosts — is ever a target.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

#: Characters that would end a header line or a request line early.
SPLITTING = re.compile(r"[\r\n\x00]")
#: A server URL variable, ``{region}``.
_VARIABLE = re.compile(r"\{([^{}]+)\}")


def default_server_url(document: Mapping[str, Any]) -> str | None:
    """``servers[0].url`` when it is a literal, absolute http(s) URL; else ``None``.

    A templated server (``{protocol}://{host_name}/api``) is a placeholder the
    document's author filled with an example host — the Digital Twin
    Registry's defaults to ``admin-shell.io`` — so it is never a target: a
    step needs ``base_url`` for such a document. Nothing is called that the
    test did not name, or that the document does not name exactly.
    """
    url = _first_server_url(document)
    if url is None or _VARIABLE.search(url):
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return url.rstrip("/")


def _first_server_url(document: Mapping[str, Any], substitute: bool = False) -> str | None:
    servers = document.get("servers")
    first = servers[0] if isinstance(servers, list) and servers else None
    if not isinstance(first, Mapping) or not isinstance(first.get("url"), str):
        return None
    url: str = first["url"]
    if not substitute:
        return url
    variables = first.get("variables") if isinstance(first.get("variables"), Mapping) else {}

    def default(match: re.Match[str]) -> str:
        entry = variables.get(match.group(1)) if variables else None
        value = entry.get("default") if isinstance(entry, Mapping) else None
        return str(value) if value is not None else match.group(0)

    return _VARIABLE.sub(default, url)


def server_base_path(document: Mapping[str, Any]) -> str:
    """The path part of ``servers[0].url``, variables at their defaults (``/api/v3``), or ``""``."""
    url = _first_server_url(document, substitute=True)
    if url is None:
        return ""
    path = urlsplit(url).path if "://" in url else url.split("?", 1)[0]
    return "" if "{" in path else path.rstrip("/")


def check_base_url(base_url: str) -> list[str]:
    """Why *base_url* cannot be a request's base, if it cannot."""
    if SPLITTING.search(base_url) or any(char.isspace() for char in base_url):
        return ["base_url contains whitespace or a control character"]
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return [f"base_url '{base_url}' is not an absolute http(s) URL"]
    if parts.query or parts.fragment:
        return [f"base_url '{base_url}' may not carry a query or a fragment"]
    return []

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

"""Credentials taken out of what a run writes down, by the name they are filed under.

Value masking (:mod:`tractusx_testlab.logging.masking`) catches a secret the run
knows about wherever it turns up, but only once it knows: an EDR token is in the
body of the response that delivers it before any step could register it, a
token endpoint's answer is traced the moment it arrives, and a secret shorter
than :data:`~tractusx_testlab.logging.masking.MIN_SECRET_LENGTH` is never masked
by value at all. A credential is filed under a name that says what it is —
``authorization``, ``client_secret``, ``refreshToken`` — so a document is also
redacted by key: a header map, a JSON body, an urlencoded form, a step's inputs.

Names are compared normalised — the last segment of a JSON-LD term or a dotted
name (``https://w3id.org/edc/v0.0.1/ns/authorization``, ``tx-auth:refreshToken``,
``header:X-Api-Key``, ``infrastructure.sut.connector.api_key``), lower-cased,
without ``-`` and ``_`` — so one entry
covers every spelling a connector or a test uses for the same field.

The header names here are the names a credential is *sent* under, which is a
set that grows with the run: a binding presents its API key in whatever header
it is configured for, and :func:`register_secret_header` adds that name for
every record the process writes from then on.
"""

from __future__ import annotations

import re
import threading
from typing import Any
from urllib.parse import parse_qsl, urlencode

from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.logging.masking import mask

#: Header names whose value never reaches what is written down. Matched
#: case-insensitively against the whole name: the point is that a bearer token or
#: an API key must not be written to a file an operator will paste into an issue.
#: One list for every record — it is handed to the tracer for the calls it
#: records and used for the account a step gives of itself, because the SDK's own
#: default set is close but not identical, and one run must not redact two ways.
SECRET_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "x-api-secret",
        "x-auth-token",
        "apikey",
        "api-key",
        "cookie",
        "set-cookie",
    }
)

#: Field names, normalised, whose value is a credential wherever it appears.
SECRET_KEYS: frozenset[str] = frozenset(
    {
        "accesstoken",
        "apikey",
        "authcode",
        "authkey",
        "authorization",
        "clientsecret",
        "edrtoken",
        "idtoken",
        "password",
        "refreshtoken",
        "secret",
        "token",
    }
)

_TERM_SEPARATORS = re.compile(r"[/#:.]")
_FORM = re.compile(r"^[^\s{}\[\]=&]+=[^\s&]*(?:&[^\s{}\[\]=&]+=[^\s&]*)*$")

_lock = threading.Lock()
_extra_headers: set[str] = set()


def _normalised(name: object) -> str:
    """``tx-auth:refreshToken`` → ``refreshtoken``; ``X-Api-Key`` → ``xapikey``."""
    term = _TERM_SEPARATORS.split(str(name))[-1]
    return term.lower().replace("-", "").replace("_", "")


def register_secret_header(name: str | None) -> None:
    """Redact header *name* from now on — a binding's configured ``api_key_header``."""
    if name and name.strip():
        with _lock:
            _extra_headers.add(name.strip().lower())


def forget_secret_headers() -> None:
    """Drop every registered header name. For tests; a run never needs to."""
    with _lock:
        _extra_headers.clear()


def secret_headers() -> frozenset[str]:
    """Every header name redacted by name: the fixed set and those registered since."""
    with _lock:
        return SECRET_HEADERS | frozenset(_extra_headers)


def is_secret_key(name: object) -> bool:
    """Whether a field or header called *name* holds a credential."""
    key = _normalised(name)
    if key in SECRET_KEYS:
        return True
    return key in {_normalised(header) for header in secret_headers()}


def redact_secrets(value: Any) -> Any:
    """*value* with every credential-named field replaced by the tracer's marker.

    Walks dicts and lists; an urlencoded form body is parsed, redacted and put
    back together. A JSON body arrives already parsed (the tracer parses what it
    records), and any other string is returned as it is — redaction is by name,
    and a string has none.
    """
    if isinstance(value, dict):
        return {
            key: (
                REDACTED_VALUE
                if is_secret_key(key) and item not in (None, "")
                else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str) and _FORM.match(value):
        pairs = parse_qsl(value, keep_blank_values=True)
        if any(is_secret_key(key) for key, _ in pairs):
            return urlencode(
                [
                    (key, REDACTED_VALUE if is_secret_key(key) and item else item)
                    for key, item in pairs
                ],
                safe="*",
            )
    return value


def written(value: Any) -> Any:
    """*value* as any record a reader is handed shows it: redacted by key, masked by value."""
    return mask(redact_secrets(value))

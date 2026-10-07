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
redacted by key: a header map, a JSON body, an urlencoded form, a step's inputs,
and the query of a URL (``?access_token=``). Which names those are is
:mod:`~tractusx_testlab.logging.wire.secret_names`.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, unquote_plus, urlencode, urlsplit, urlunsplit

from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.logging.masking import mask
from tractusx_testlab.logging.wire.secret_names import (
    SECRET_HEADERS,
    forget_secret_headers,
    is_secret_header,
    is_secret_key,
    is_text_only_key,
    register_secret_header,
    secret_headers,
)

__all__ = [
    "SECRET_HEADERS",
    "forget_secret_headers",
    "is_secret_header",
    "is_secret_key",
    "redact_secrets",
    "redact_url",
    "register_secret_header",
    "secret_headers",
    "written",
]

_FORM = re.compile(r"^[^\s{}\[\]=&]+=[^&\r\n]*(?:&[^\s{}\[\]=&]+=[^&\r\n]*)*\Z")
_URL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://\S+$")


def redact_secrets(value: Any) -> Any:
    """*value* with every credential-named field replaced by the tracer's marker.

    Walks dicts and lists; an urlencoded form body is parsed, redacted and put
    back together, and a URL has its credential-named query parameters
    redacted (:func:`redact_url`). A JSON body arrives already parsed (the
    tracer parses what it records), and any other string is returned as it is —
    redaction is by name, and a string has none.
    """
    if isinstance(value, dict):
        return {
            key: REDACTED_VALUE if _holds_credential(key, item) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str) and _URL.match(value):
        return redact_url(value)
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


def _holds_credential(key: Any, item: Any) -> bool:
    """Whether *item*, filed under *key*, is a credential — a flag never is."""
    if item in (None, "") or isinstance(item, bool) or not is_secret_key(key):
        return False
    return isinstance(item, str) or not is_text_only_key(key)


def redact_url(url: str) -> str:
    """*url* with the value of every credential-named query parameter as ``***``.

    ``?api_key=…``, ``&access_token=…``, a password in the user-info. Anything
    else about the URL is left exactly as written: the address is the evidence
    of where a call went, and re-encoding it would report a request nobody sent.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    query = "&".join(_redacted_pair(pair) for pair in parts.query.split("&"))
    netloc = parts.netloc
    userinfo, at, host = netloc.rpartition("@")
    if at and ":" in userinfo:
        netloc = f"{userinfo.split(':', 1)[0]}:{REDACTED_VALUE}@{host}"
    if query == parts.query and netloc == parts.netloc:
        return url
    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def _redacted_pair(pair: str) -> str:
    name, equals, value = pair.partition("=")
    if equals and value and is_secret_key(unquote_plus(name)):
        return f"{name}={REDACTED_VALUE}"
    return pair


def written(value: Any) -> Any:
    """*value* as any record a reader is handed shows it: redacted by key, masked by value."""
    return mask(redact_secrets(value))

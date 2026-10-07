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

"""Which names a credential is filed under — a field's, a header's, a parameter's.

A credential is rarely called just ``password``. A run meets ``sut_password``,
``bearerToken``, ``edc_api_key``, ``client_assertion``, ``X-Vault-Token`` and
``Ocp-Apim-Subscription-Key``, and a list of exact names is out of date the day
it is written. So a name is matched by what it *contains*, after normalising it
— the last segment of a JSON-LD term or a dotted name
(``https://w3id.org/edc/v0.0.1/ns/authorization``, ``tx-auth:refreshToken``,
``header:X-Api-Key``, ``infrastructure.sut.connector.api_key``), lower-cased,
without ``-`` and ``_``.

Matching by part has the opposite failure: ``token_type``, ``token_url``,
``api_key_header`` and ``has_secret`` name something *about* a credential — its
kind, where to get one, which header carries it, whether there is one — and
hide nothing. Those shapes are excluded explicitly (:data:`_ABOUT_SUFFIXES`,
:data:`_ABOUT_PREFIX`), and a value that is only a flag is never a credential.

Header names are matched wider still: any header whose name mentions a token, a
secret, a key, auth, a cookie or a session is a credential's carrier
(``X-Forwarded-Access-Token``), except the few standard ones that only *talk
about* authentication. The set also grows with the run: a binding presents its
API key in whatever header it is configured for, and
:func:`register_secret_header` adds that name for every record the process
writes from then on.
"""

from __future__ import annotations

import re
import threading
from functools import lru_cache

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

#: Parts of a normalised name that make it a credential wherever they occur.
SECRET_PARTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "credential",
    "privatekey",
    "authorization",
    "subscriptionkey",
)

#: Whole normalised names that are a credential — too short or too common to
#: look for inside another name.
SECRET_NAMES: frozenset[str] = frozenset(
    {"authcode", "authkey", "bearer", "codeverifier", "cookie", "jwt", "pwd", "setcookie"}
)

#: A name ending like this is a signed assertion — RFC 7523's ``assertion``,
#: ``client_assertion``. Only one that *holds text* is: a check's ``assertion``
#: in a result is the check, not a credential (:func:`is_text_only_key`).
_ASSERTION = "assertion"

#: Endings of a name that says something *about* a credential and holds none.
_ABOUT_SUFFIXES: tuple[str, ...] = (
    "type",
    "types",
    "url",
    "urls",
    "uri",
    "endpoint",
    "header",
    "headers",
    "id",
    "ids",
    "name",
    "names",
    "path",
    "hint",
    "method",
    "expiresin",
    "expiresat",
    "expiry",
    "ttl",
    "length",
    "count",
    "format",
    "fields",
    "params",
)

#: A flag about a credential: ``has_secret``, ``isToken``, ``require_api_key``.
_ABOUT_PREFIX = re.compile(r"^(?:has|is|use|uses|require|requires)(?:[_\-]|(?=[A-Z]))")

#: Parts of a header name that make it a credential's carrier.
_HEADER_PARTS: tuple[str, ...] = ("token", "secret", "key", "auth", "cookie", "session")

#: Standard headers whose names mention authentication and carry none.
_HARMLESS_HEADERS: frozenset[str] = frozenset(
    {
        "wwwauthenticate",
        "proxyauthenticate",
        "accesscontrolallowcredentials",
        "accesscontrolallowheaders",
        "accesscontrolexposeheaders",
        "accesscontrolrequestheaders",
    }
)

_TERM_SEPARATORS = re.compile(r"[/#:.]")

_lock = threading.Lock()
_extra_headers: set[str] = set()
_extra_keys: frozenset[str] = frozenset()


def _term(name: object) -> str:
    """The last segment of a JSON-LD term or a dotted name, as written."""
    return _TERM_SEPARATORS.split(str(name))[-1].strip()


def normalised(name: object) -> str:
    """``tx-auth:refreshToken`` → ``refreshtoken``; ``X-Api-Key`` → ``xapikey``."""
    return _term(name).lower().replace("-", "").replace("_", "")


def register_secret_header(name: str | None) -> None:
    """Redact header *name* from now on — a binding's configured ``api_key_header``."""
    global _extra_keys
    if name and name.strip():
        with _lock:
            _extra_headers.add(name.strip().lower())
            _extra_keys = frozenset(normalised(header) for header in _extra_headers)


def forget_secret_headers() -> None:
    """Drop every registered header name. For tests; a run never needs to."""
    global _extra_keys
    with _lock:
        _extra_headers.clear()
        _extra_keys = frozenset()


def secret_headers() -> frozenset[str]:
    """Every header name redacted by its exact name: the fixed set and those registered since."""
    with _lock:
        return SECRET_HEADERS | frozenset(_extra_headers)


def is_secret_key(name: object) -> bool:
    """Whether a field, a parameter or a header called *name* holds a credential."""
    term = _term(name)
    return _is_credential_name(term) or normalised(term) in _extra_keys


def is_text_only_key(name: object) -> bool:
    """Whether *name* is a credential only when it holds text (see :data:`_ASSERTION`)."""
    return normalised(name) == _ASSERTION


def is_secret_header(name: object) -> bool:
    """Whether a header called *name* carries a credential — by name, part or registration."""
    lowered = str(name).strip().lower()
    if lowered in secret_headers():
        return True
    key = lowered.replace("-", "").replace("_", "")
    if key in _HARMLESS_HEADERS:
        return False
    return any(part in key for part in _HEADER_PARTS) or is_secret_key(name)


@lru_cache(maxsize=4096)
def _is_credential_name(term: str) -> bool:
    if _ABOUT_PREFIX.match(term):
        return False
    key = term.lower().replace("-", "").replace("_", "")
    if key in SECRET_NAMES or key.endswith(_ASSERTION):
        return True
    if not any(part in key for part in SECRET_PARTS):
        return False
    return not key.endswith(_ABOUT_SUFFIXES)

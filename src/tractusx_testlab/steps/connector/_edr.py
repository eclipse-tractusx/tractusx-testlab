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

"""An EDR as the run holds it: its address readable, its tokens handles.

The engine's connector negotiates, and the provider hands it an Endpoint Data
Reference — a data-plane address and the token that opens it, often with a
refresh token beside it. Whoever holds the token reads the provider's data as
the engine's participant until it expires, and with the refresh token for
longer. So the token is a credential the run was issued
(:data:`~tractusx_testlab.security.credentials.ISSUED`): a step's output
carries it as a :class:`~tractusx_testlab.security.credentials.Credential`
bound to the data plane's own origin. The data-plane steps send it there;
``http/http_request`` may send it there as a header; nothing turns it into
text — not a log line, not a request body, not a mock's reply.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.logging.wire.redaction import is_secret_key
from tractusx_testlab.security.credentials import Credential, issued_credential

__all__ = ["EDR_TOKEN", "Credential", "edr_token", "issued_data_address"]

#: The reference name every EDR token handle reports in an error.
EDR_TOKEN = "edr_token"

#: Data-address keys naming the address a token opens, compact or expanded.
_ENDPOINT = "endpoint"
_REFRESH_ENDPOINT = "refreshendpoint"


def _local(key: object) -> str:
    """``https://w3id.org/edc/v0.0.1/ns/endpoint`` and ``edc:endpoint`` as ``endpoint``."""
    text = str(key)
    for separator in ("#", "/", ":"):
        text = text.rsplit(separator, 1)[-1]
    return text.lower()


def _address_of(document: dict[str, Any], local: str) -> str:
    return next((str(v) for k, v in document.items() if _local(k) == local and v), "")


def issued_data_address(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """*document* with every credential in it a handle bound to its data plane.

    The token opens the data-plane ``endpoint``; a refresh token opens the
    ``refreshEndpoint`` it came with, and nothing when there is none. Every
    other key — the address, its type, its expiry — is kept as it was.
    """
    if not isinstance(document, dict):
        return document
    endpoint = _address_of(document, _ENDPOINT)
    refresh = _address_of(document, _REFRESH_ENDPOINT)
    return {
        key: issued_credential(
            value,
            name=f"data_address.{_local(key)}",
            url=refresh if _local(key).startswith("refresh") else endpoint,
        )
        if isinstance(value, str | Credential) and value and is_secret_key(key)
        else value
        for key, value in document.items()
    }


def edr_token(token: object, endpoint: object) -> Credential | None:
    """The handle an EDR's *token* is published as, bound to *endpoint*'s origin."""
    return issued_credential(token, name=EDR_TOKEN, url=endpoint)

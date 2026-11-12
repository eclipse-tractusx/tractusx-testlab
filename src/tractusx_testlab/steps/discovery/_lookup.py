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

"""What the discovery steps share: the engine's token, and reading the services' answers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tractusx_testlab.logging.masking import register_secret
from tractusx_testlab.models import StepExecutionError
from tractusx_testlab.steps import http_client

if TYPE_CHECKING:
    from tractusx_testlab.models.domain.discovery_capability import DiscoveryBinding

__all__ = ["client_token", "endpoints_for", "quoted"]

#: How much of a refusing server's body an error message quotes.
_QUOTED_BODY = 300


async def client_token(step_type: str, binding: DiscoveryBinding, timeout: float, run: str) -> str:
    """A token for the engine's technical user, or ``""`` when none is configured."""
    if not binding.token_url:
        return ""
    if not binding.client_id:
        raise StepExecutionError(
            step_type,
            "infrastructure.engine.discovery.token_url is set but client_id is not. "
            "The discovery services are reached with the engine's technical user; "
            "bind its client_id and client_secret, or leave token_url empty.",
        )
    if binding.client_secret:
        register_secret(binding.client_secret, run=run, explicit=True)
    form = {
        "grant_type": "client_credentials",
        "client_id": binding.client_id,
        "client_secret": binding.client_secret,
    }
    if binding.scope:
        form["scope"] = binding.scope
    resp = await http_client.request("POST", binding.token_url, data=form, timeout=timeout)
    body = http_client.body_of(resp)
    token = body.get("access_token") if isinstance(body, dict) else None
    if resp.status_code >= 400 or not isinstance(token, str) or not token:
        raise StepExecutionError(
            step_type,
            f"the identity provider at {binding.token_url} gave the engine's technical "
            f"user '{binding.client_id}' no token (HTTP {resp.status_code}). Check "
            f"infrastructure.engine.discovery.client_id and client_secret.",
        )
    return token


def endpoints_for(document: Any, bpnl: str) -> list[str]:
    """Every endpoint *document* lists for *bpnl*, once each and in the order given.

    The EDC Discovery answers ``[{"bpn": …, "connectorEndpoint": [...]}]``; an
    entry for another BPN is ignored, and a BPN is compared without regard to
    case, since a partner's registration and a test's spelling may differ there
    and nowhere else.
    """
    wanted = bpnl.strip().upper()
    found: list[str] = []
    for entry in document if isinstance(document, list) else []:
        if not isinstance(entry, dict) or str(entry.get("bpn", "")).strip().upper() != wanted:
            continue
        endpoints = entry.get("connectorEndpoint") or []
        for endpoint in [endpoints] if isinstance(endpoints, str) else endpoints:
            if isinstance(endpoint, str) and endpoint and endpoint not in found:
                found.append(endpoint)
    return found


def quoted(document: Any) -> str:
    """*document* shortened for an error message."""
    text = str(document) if document not in (None, "") else "nothing"
    return text if len(text) <= _QUOTED_BODY else f"{text[:_QUOTED_BODY]}…"

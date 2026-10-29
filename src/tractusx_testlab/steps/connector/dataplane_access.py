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

"""Reaching a data plane: its address, its EDR token, and the one way a call is sent.

``connector/dataplane/http_request`` and ``labs/connector/dataplane/api_request``
both call a data plane; they share where it is, which token opens it, and how
the token travels — released for the data plane's own origin only, recorded
as ``***``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import Field
from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.security.credentials import reveal
from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.connector._edr import Credential
from tractusx_testlab.steps.step_contract import StepParams
from tractusx_testlab.syntax.context_vars import EDR_TOKEN

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class DataplaneAddressParams(StepParams):
    """Where a data-plane call goes and with which token — every data-plane step takes it.

    Left alone, both the URL and the token come from whichever step completed
    the transfer — every step publishes all of its return outputs, and the
    steps that end a transfer all return the ``dataplane_url``/``edr_token``
    pair under exactly these names.
    """

    dataplane_url: Any = Field(
        default=None,
        description=(
            "Data-plane URL, or a data address object to read it from; falls back "
            "to the 'dataplane_url' context variable."
        ),
    )
    edr_token: Credential | str | None = Field(
        default=None,
        description=(
            "EDR authorization token; falls back to the 'edr_token' context variable "
            "when omitted. An explicit '' asks for the call to be made with no token "
            "at all — e.g. a negative-path test proving the endpoint is protected — "
            "and is honoured as given rather than falling back."
        ),
    )

    def resolved_token(self, fallback: object) -> object:
        """The token to send, or '' if the test explicitly asked for none.

        ``None`` means the test left the field out, so the context variable a
        prior transfer published is used. An explicit ``''`` is a test asking
        for the call to carry no token — the negative-path case a `falsy or
        fallback` read would silently defeat by substituting a stale token from
        an earlier step in the same run.
        """
        return fallback if self.edr_token is None else self.edr_token

    def resolved_endpoint(self, fallback: Any) -> str:
        """The data plane's URL, from whichever form the data address arrived in."""
        endpoint = self.dataplane_url or fallback
        if isinstance(endpoint, dict):
            endpoint = endpoint.get("endpoint") or endpoint.get("baseUrl")
        return str(endpoint or "")


@dataclass(frozen=True, slots=True)
class DataplaneExchange:
    """A call made through a data plane: the answer, the URL and the headers as recorded."""

    response: httpx.Response
    url: str
    recorded_headers: dict[str, str]


async def call_dataplane(
    context: StepContext,
    address: DataplaneAddressParams,
    url: str,
    *,
    method: str,
    headers: dict[str, str],
    timeout: float,
    follow_redirects: bool | None = None,
    **payload: Any,
) -> DataplaneExchange:
    """Call *url* on a data plane with the EDR token *address* resolves to.

    The one way a step sends through a data plane: the token is released for
    the data plane's own origin only, recorded as ``***``, and a redirect is
    not followed while a credential handle travels (unless the caller decides).
    """
    # An EDR token is a handle that opens for its own data plane only.
    held = address.resolved_token(context.get_variable(EDR_TOKEN, ""))
    token = reveal(held, url, context.config.credential_release)
    sent = {"Authorization": token, **headers}
    resp = await http_client.request(
        method,
        url,
        headers=sent,
        timeout=timeout,
        follow_redirects=(
            not isinstance(held, Credential) if follow_redirects is None else follow_redirects
        ),
        **payload,
    )
    recorded = {**sent, "Authorization": REDACTED_VALUE} if token else sent
    return DataplaneExchange(resp, url, recorded)

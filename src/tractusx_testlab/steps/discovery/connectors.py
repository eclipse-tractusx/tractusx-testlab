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

"""discovery/connectors_by_bpn — where a business partner's connectors are.

A Catena-X consumer holds a BPN, not an address. The dataspace answers the
question in two hops:

1. The **Discovery Finder** is asked for the discovery service of a key type
   (``POST {"types": ["bpn"]}``) and answers with the address of the
   **EDC Discovery** service.
2. The EDC Discovery is asked for the BPN (``POST ["BPNL…"]``) and answers
   with every connector endpoint registered for it.

What comes back is the DSP *root* of each connector. Its protocol version is a
third question, put to the connector itself, which is what
``connector/consumer/discover_connector`` asks — so this step's
``counter_party_address`` is written to be handed straight to that one. Between
them a test goes from a BPN alone to an address and protocol a catalog query
can use, which is what a use case such as CCM expects a consumer to do.

The finder's address and the engine's technical user are the deployment's, and
come from ``infrastructure.engine.discovery``. A test may name an EDC Discovery
directly (``edc_discovery_url``), which skips the finder — a mock, or a
dataspace that publishes the service's address instead of a finder.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.logging.masking import register_secret
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition, StepExecutionError
from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.discovery._lookup import client_token, endpoints_for, quoted
from tractusx_testlab.steps.shared_models import HttpTransportParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.models.domain.discovery_capability import DiscoveryBinding
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

__all__ = [
    "BPN_DISCOVERY_TYPE",
    "ConnectorsByBpnOutput",
    "ConnectorsByBpnParams",
    "ConnectorsByBpnStep",
]

#: Key type the Discovery Finder files the EDC Discovery under.
BPN_DISCOVERY_TYPE = "bpn"

_AUTHORIZATION = "Authorization"


class ConnectorsByBpnParams(HttpTransportParams):
    """Input contract of ``discovery/connectors_by_bpn``."""

    bpnl: str = Field(
        min_length=1,
        description="BPN of the business partner whose connectors are looked up.",
    )
    discovery_type: str = Field(
        default=BPN_DISCOVERY_TYPE,
        description=(
            "Key type the Discovery Finder is asked for. 'bpn' is the EDC Discovery; "
            "change it only for a dataspace that files the service under another type."
        ),
    )
    discovery_finder_url: str = Field(
        default="",
        description=(
            "Discovery Finder search URL to ask instead of "
            "'infrastructure.engine.discovery.finder_url'."
        ),
    )
    edc_discovery_url: str = Field(
        default="",
        description=(
            "EDC Discovery URL to ask directly. When given, the Discovery Finder is not "
            "asked at all."
        ),
    )
    access_token: str = Field(
        default="",
        description=(
            "Bearer token to call the discovery services with, instead of the one the "
            "engine obtains with 'infrastructure.engine.discovery' client credentials."
        ),
    )


class ConnectorsByBpnOutput(StepPayload):
    """Output contract of ``discovery/connectors_by_bpn``.

    ``connector_endpoints`` is every endpoint the BPN is registered with, in
    the order the service answered; ``counter_party_address`` is the first of
    them, for the common case of a partner that runs one connector.
    """

    connector_endpoints: list[str] = Field(
        description="Every connector endpoint the EDC Discovery holds for the BPN."
    )
    counter_party_address: str = Field(
        description="The first of them — the DSP root to hand to connector discovery."
    )
    edc_discovery_url: str = Field(
        description="EDC Discovery URL that was asked, as the finder answered it."
    )
    discovery: Any = Field(description="The EDC Discovery response document, unchanged.")


@step("discovery/connectors_by_bpn")
class ConnectorsByBpnStep(BaseStep[ConnectorsByBpnParams, ConnectorsByBpnOutput]):
    """Look up a business partner's connector endpoints from its BPN.

    Asks the Discovery Finder for the EDC Discovery, then the EDC Discovery for
    the BPN. A BPN the service holds no connector for fails the step, naming
    the service asked: an empty address handed on would surface three steps
    later as a refused connection that says nothing about why.
    """

    params_model = ConnectorsByBpnParams
    output_model = ConnectorsByBpnOutput

    async def execute(
        self,
        params: ConnectorsByBpnParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[ConnectorsByBpnOutput]:
        binding = context.infrastructure.engine.discovery
        timeout = params.timeout_or(context.config.default_timeout_s)
        run = str(context.job.job_id)

        token = params.access_token or await client_token(self.step_type, binding, timeout, run)
        headers = dict(params.headers)
        if token:
            register_secret(token, run=run, explicit=True)
            headers[_AUTHORIZATION] = f"Bearer {token}"

        edc_discovery_url = params.edc_discovery_url or await self._find_edc_discovery(
            params, binding, headers, timeout
        )

        body = [params.bpnl]
        resp = await http_client.request(
            "POST",
            edc_discovery_url,
            json=body,
            headers=headers,
            timeout=timeout,
            secret_headers=(_AUTHORIZATION,),
        )
        document = http_client.body_of(resp)
        self._refuse_error_status(resp.status_code, document, "EDC Discovery", edc_discovery_url)

        endpoints = endpoints_for(document, params.bpnl)
        if not endpoints:
            raise StepExecutionError(
                self.step_type,
                f"the EDC Discovery at {edc_discovery_url} holds no connector endpoint for "
                f"BPN '{params.bpnl}'. A partner reachable by BPN registers its connector "
                f"there; it answered: {quoted(document)}",
            )

        logger.info(
            "BPN %s has %d connector endpoint(s) at %s",
            params.bpnl,
            len(endpoints),
            edc_discovery_url,
        )
        return StepOutput(
            value=ConnectorsByBpnOutput(
                connector_endpoints=endpoints,
                counter_party_address=endpoints[0],
                edc_discovery_url=edc_discovery_url,
                discovery=document,
            ),
            request=HttpRequest(method="POST", url=edc_discovery_url, body=body),
            response=HttpResponse(
                status_code=resp.status_code, headers=dict(resp.headers), body=document
            ),
        )

    async def _find_edc_discovery(
        self,
        params: ConnectorsByBpnParams,
        binding: DiscoveryBinding,
        headers: dict[str, str],
        timeout: float,
    ) -> str:
        """Ask the Discovery Finder where the discovery service of *discovery_type* is."""
        finder_url = params.discovery_finder_url or binding.finder_url
        if not finder_url:
            raise StepExecutionError(
                self.step_type,
                "no Discovery Finder to ask: bind infrastructure.engine.discovery.finder_url, "
                "or give the step 'discovery_finder_url' or 'edc_discovery_url'.",
            )
        resp = await http_client.request(
            "POST",
            finder_url,
            json={"types": [params.discovery_type]},
            headers=headers,
            timeout=timeout,
            secret_headers=(_AUTHORIZATION,),
        )
        document = http_client.body_of(resp)
        self._refuse_error_status(resp.status_code, document, "Discovery Finder", finder_url)

        entries = document.get("endpoints") if isinstance(document, dict) else None
        addresses = [
            entry["endpointAddress"]
            for entry in entries or []
            if isinstance(entry, dict)
            and entry.get("type") == params.discovery_type
            and isinstance(entry.get("endpointAddress"), str)
            and entry["endpointAddress"]
        ]
        if not addresses:
            raise StepExecutionError(
                self.step_type,
                f"the Discovery Finder at {finder_url} names no discovery service of type "
                f"'{params.discovery_type}'. It answered: {quoted(document)}",
            )
        return addresses[0]

    def _refuse_error_status(self, status: int, document: Any, service: str, url: str) -> None:
        """Fail on a refusal, quoting what the service said."""
        if status >= 400:
            raise StepExecutionError(
                self.step_type,
                f"the {service} at {url} refused the request with HTTP {status}: "
                f"{quoted(document)}",
            )

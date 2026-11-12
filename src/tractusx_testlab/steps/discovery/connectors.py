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
question in two hops: the **Discovery Finder** names the **EDC Discovery**
(key type ``bpn``), and the EDC Discovery names every connector endpoint
registered for the BPN. Both hops are the SDK's ``ConnectorDiscoveryService``;
the step builds it from ``infrastructure.engine.discovery`` and reads what it
answers.

What comes back is the DSP *root* of each connector. Its protocol version is a
third question, put to the connector itself, which is what
``connector/consumer/discover_connector`` asks — so ``counter_party_address`` is
written to be handed straight to that one. Between them a test goes from a BPN
alone to an address and protocol a catalog query can use, which is what a use
case such as CCM expects a consumer to do.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition, StepExecutionError
from tractusx_testlab.steps.discovery._lookup import asked_url, build_services, call
from tractusx_testlab.steps.shared_models import StepParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
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


class ConnectorsByBpnParams(StepParams):
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
            "'infrastructure.engine.discovery.finder_url' — a mock's, most of all. The "
            "binding's technical user still signs the requests."
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


@step("discovery/connectors_by_bpn")
class ConnectorsByBpnStep(BaseStep[ConnectorsByBpnParams, ConnectorsByBpnOutput]):
    """Look up a business partner's connector endpoints from its BPN.

    A BPN the EDC Discovery holds no connector for fails the step, naming the
    service asked: an empty address handed on would surface three steps later
    as a refused connection that says nothing about why.
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
        finder_url = params.discovery_finder_url or binding.finder_url
        if not finder_url:
            raise StepExecutionError(
                self.step_type,
                "no Discovery Finder to ask: bind infrastructure.engine.discovery.finder_url, "
                "or give the step 'discovery_finder_url'.",
            )
        services = await build_services(
            self.step_type, binding, finder_url, str(context.job.job_id)
        )
        discovery = services.connectors(params.discovery_type)

        found: Any = await call(
            self.step_type,
            f"the EDC Discovery behind the Discovery Finder at {finder_url}",
            discovery.find_connector_by_bpn,
            params.bpnl,
        )
        edc_discovery_url = asked_url(discovery.get_cache_status(), params.discovery_type)
        endpoints = _unique(found)
        if not endpoints:
            raise StepExecutionError(
                self.step_type,
                f"the EDC Discovery at {edc_discovery_url or finder_url} holds no connector "
                f"endpoint for BPN '{params.bpnl}'. A partner reachable by BPN registers "
                f"its connector there.",
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
            )
        )


def _unique(found: Any) -> list[str]:
    """The endpoints the SDK returned, once each and in order; none for ``None``."""
    endpoints = [found] if isinstance(found, str) else found or []
    unique: list[str] = []
    for endpoint in endpoints:
        if isinstance(endpoint, str) and endpoint and endpoint not in unique:
            unique.append(endpoint)
    return unique

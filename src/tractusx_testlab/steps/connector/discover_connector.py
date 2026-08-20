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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Connector discovery — resolving a counter-party's DSP endpoint from its BPN.

Saturn connectors expose ``/v4alpha/connectordiscovery/dspversionparams``: given
a BPN, the connector answers with the DSP endpoint, the counter-party ID and the
protocol version to address it under.  Every later step in a chain — catalog,
negotiation, transfer — takes those three values as inputs, so a Saturn TCK can
start from a BPN alone rather than from a hard-coded endpoint.

Jupiter connectors have no such endpoint and the SDK's Jupiter consumer service
has no such method, which is why the step registers for ``saturn`` only.  On a
Jupiter TCK it does not resolve at all, and the compiler says so, rather than
the step failing halfway through a run against a connector that was never going
to answer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.models import (
    HttpRequest,
    HttpResponse,
    StepDefinition,
    StepExecutionError,
)
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.shared_models import StepParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

__all__ = [
    "EDC_NAMESPACE",
    "DiscoverConnectorOutput",
    "DiscoverConnectorParams",
    "DiscoverConnectorStep",
]

#: Namespace the connector prefixes its discovery response keys with.  The same
#: default the SDK uses, spelled out here because it is a step parameter.
EDC_NAMESPACE = "https://w3id.org/edc/v0.0.1/ns/"

#: The three keys a discovery response carries, in the order they are read.
_COUNTER_PARTY_ADDRESS = "counterPartyAddress"
_COUNTER_PARTY_ID = "counterPartyId"
_PROTOCOL = "protocol"


class DiscoverConnectorParams(StepParams):
    """Input contract of ``connector/consumer/discover_connector``."""

    bpnl: str = Field(description="BPN of the counter-party whose connector is discovered.")
    counter_party_address: str = Field(
        default="",
        description=(
            "DSP endpoint to discover against; when omitted the connector resolves it "
            "from the BPN alone."
        ),
    )
    namespace: str = Field(
        default=EDC_NAMESPACE,
        description="Namespace the response keys are prefixed with; bare keys are read too.",
    )


class DiscoverConnectorOutput(StepPayload):
    """Output contract of ``connector/consumer/discover_connector``.

    The raw document and the three values read out of it stand side by side: a
    test asserts on ``discovery`` and the next step reads ``counter_party_address``
    / ``counter_party_id`` / ``protocol`` without knowing which spelling — bare
    or namespaced — the connector happened to answer with.
    """

    discovery: Any = Field(description="The discovery response document, unchanged.")
    counter_party_address: str = Field(
        description="DSP endpoint the counter-party is addressed at."
    )
    counter_party_id: str = Field(description="ID the counter-party identifies itself as.")
    protocol: str = Field(
        description="DSP protocol version the endpoint speaks, e.g. 'dataspace-protocol-http:2025-1'."
    )


@step("connector/consumer/discover_connector", dataspace_version="saturn")
class DiscoverConnectorStep(BaseStep[DiscoverConnectorParams, DiscoverConnectorOutput]):
    """Discover a counter-party's DSP endpoint, ID and protocol from its BPN.

    **Saturn only.** The endpoint this calls is a Saturn addition and the SDK
    exposes it on the Saturn consumer service alone, so the step is registered
    for that release and a script on any other cannot resolve it.
    """

    params_model = DiscoverConnectorParams
    output_model = DiscoverConnectorOutput

    async def execute(
        self,
        params: DiscoverConnectorParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DiscoverConnectorOutput]:
        consumer = context.dataspace.consumer()
        discover = getattr(consumer, "discover_connector_protocol", None)
        if discover is None:
            # Reachable only if the step is resolved outside its registered
            # version; say which service is missing rather than raise AttributeError.
            raise StepExecutionError(
                self.step_type,
                "the bound connector service does not offer connector discovery. "
                "The step is Saturn-only and the service is not a Saturn one.",
            )

        url = context.dataspace.consumer_endpoint_url("connector_discovery")
        request = HttpRequest(method="POST", url=url, body=params.model_dump(mode="json"))

        # One round trip, not two: `get_discovery_info` would resolve the three
        # values but drop the document the test asserts on, and calling both
        # would discover twice.
        document = await sdk_call.run(
            discover,
            bpnl=params.bpnl,
            counter_party_address=params.counter_party_address or None,
        )
        if not isinstance(document, dict):
            raise StepExecutionError(
                self.step_type,
                f"the connector returned no discovery document for BPN '{params.bpnl}' "
                f"from {url}. The step declares an endpoint, an ID and a protocol, "
                f"and has none of them.",
            )

        return StepOutput(
            value=DiscoverConnectorOutput(
                discovery=document,
                counter_party_address=self._read(document, _COUNTER_PARTY_ADDRESS, params),
                counter_party_id=self._read(document, _COUNTER_PARTY_ID, params),
                protocol=self._read(document, _PROTOCOL, params),
            ),
            request=request,
            response=HttpResponse(status_code=200, body=document),
        )

    def _read(self, document: dict, key: str, params: DiscoverConnectorParams) -> str:
        """Read *key* from the response, namespaced spelling first.

        A connector may expand the response into JSON-LD or leave the keys bare,
        and both are the same answer.  A key that is present under neither
        spelling fails the step here, naming what was looked for, rather than
        publishing an empty endpoint that the next step reports as a refused
        connection.
        """
        for spelling in (f"{params.namespace}{key}", key):
            if spelling in document:
                return str(document[spelling])
        raise StepExecutionError(
            self.step_type,
            f"the discovery response for BPN '{params.bpnl}' carries no '{key}' "
            f"(looked for '{params.namespace}{key}' and '{key}'). "
            f"It carries: {', '.join(sorted(document)) or 'nothing'}.",
        )

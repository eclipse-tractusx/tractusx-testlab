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

"""mock/discovery step — an EDC Discovery mock, and the Discovery Finder in front of it.

Registers ``POST /api/administration/connectors/discovery`` (the EDC Discovery
shape) so a consumer can resolve a counter-party's DSP endpoint from its BPN,
filtered to just the BPNs it asked about — mirroring the real service.

It also registers the Discovery Finder search
(``POST /api/v1.0/administration/connectors/discovery/search``), answering a
``bpn`` lookup with the mock EDC Discovery's own address, so the whole two-hop
lookup ``discovery/connectors_by_bpn`` makes runs against the mock as it would
against the dataspace. Both addresses are published as outputs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.server.inbound.run_scope import run_root
from tractusx_testlab.server.mock_registry import MockRequest, MockResponse, register_mock
from tractusx_testlab.steps.mock._models import RequiredMockIdParams
from tractusx_testlab.steps.mock.api import published_base_url
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DISCOVERY_PATH = "/api/administration/connectors/discovery"
_FINDER_PATH = "/api/v1.0/administration/connectors/discovery/search"

#: Key type the Discovery Finder files the EDC Discovery under.
_BPN_TYPE = "bpn"


class MockDiscoveryParams(RequiredMockIdParams):
    """Input contract of ``mock/discovery``.

    ``mappings`` accepts either spelling tests already use: a plain
    BPN-to-endpoint object, or a list of ``{bpn, endpoint}`` entries.
    """

    mappings: dict[str, str] = Field(
        min_length=1,
        description="BPN to EDC endpoint mapping, or a list of {bpn, endpoint} entries.",
    )

    @field_validator("mappings", mode="before")
    @classmethod
    def _entries_are_a_mapping(cls, value: Any) -> Any:
        """Fold the list-of-entries spelling into the mapping the step works with."""
        if isinstance(value, list):
            return {
                entry["bpn"]: entry["endpoint"]
                for entry in value
                if isinstance(entry, dict) and "bpn" in entry
            }
        return value


class MockDiscoveryOutput(StepPayload):
    """Output contract of ``mock/discovery``: where the two mock services answer."""

    edc_discovery_url: str = Field(description="URL of the mock EDC Discovery.")
    discovery_finder_url: str = Field(
        description="Search URL of the mock Discovery Finder, which names the mock EDC Discovery."
    )


@step("mock/discovery")
class MockDiscoveryStep(BaseStep[MockDiscoveryParams, MockDiscoveryOutput]):
    """Register a BPN Discovery Finder mock returning configured EDC endpoints.

    A consumer step can then resolve a counter-party's DSP endpoint from its BPN
    exactly as it would against the real service — the mock answers only for the
    BPNs it was asked about.
    """

    params_model = MockDiscoveryParams
    output_model = MockDiscoveryOutput

    async def execute(
        self,
        params: MockDiscoveryParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[MockDiscoveryOutput]:
        bpn_to_endpoint = params.mappings
        run = str(context.job.job_id)
        base_url = run_root(published_base_url(context), run)
        edc_discovery_url = f"{base_url}{_DISCOVERY_PATH}"

        def _discover(req: MockRequest) -> MockResponse:
            requested_bpns = (
                req.body if isinstance(req.body, list) else (req.body or {}).get("bpns", [])
            )
            if not requested_bpns:
                requested_bpns = list(bpn_to_endpoint.keys())
            result = [
                {"bpn": bpn, "connectorEndpoint": [bpn_to_endpoint[bpn]]}
                for bpn in requested_bpns
                if bpn in bpn_to_endpoint
            ]
            # Mirrors the real discovery finder, which returns a bare JSON array.
            return MockResponse(status_code=200, body=result)

        def _find(req: MockRequest) -> MockResponse:
            types = (req.body or {}).get("types", []) if isinstance(req.body, dict) else []
            endpoints = (
                [
                    {
                        "type": _BPN_TYPE,
                        "description": "TestLab mock EDC Discovery",
                        "endpointAddress": edc_discovery_url,
                        "documentation": "",
                        "resourceId": params.id,
                    }
                ]
                if not types or _BPN_TYPE in types
                else []
            )
            return MockResponse(status_code=200, body={"endpoints": endpoints})

        register_mock(_DISCOVERY_PATH, "POST", _discover, run=run)
        register_mock(_FINDER_PATH, "POST", _find, run=run)

        logger.info(
            "Registered mock discovery service '%s' with %d mappings",
            params.id,
            len(bpn_to_endpoint),
        )
        return StepOutput(
            value=MockDiscoveryOutput(
                edc_discovery_url=edc_discovery_url,
                discovery_finder_url=f"{base_url}{_FINDER_PATH}",
            )
        )

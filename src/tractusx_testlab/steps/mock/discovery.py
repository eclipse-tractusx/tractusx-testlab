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

"""mock/discovery step — the dataspace's discovery services, mocked.

Registers, under the run's own address:

* the **EDC Discovery** (``POST /api/administration/connectors/discovery``):
  a BPN's connector endpoints, filtered to the BPNs asked about;
* the **BPN Discovery** (``POST /api/v1.0/administration/connectors/bpnDiscovery/search``):
  the BPNs an identifier — a ``manufacturerPartId``, say — is registered for;
* the **Discovery Finder** (``POST /api/v1.0/administration/connectors/discovery/search``),
  which names the mock EDC Discovery for ``bpn`` and the mock BPN Discovery for
  every identifier type the mock holds.

So the lookups the ``discovery/*`` steps make through the SDK — finder first,
then the service it names — run against the mock as they would against the
dataspace. Every address is published as an output.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator

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
#: Where the SDK addresses a BPN Discovery the finder names (its ``base_path``).
_BPN_DISCOVERY_PATH = "/api/v1.0/administration/connectors/bpnDiscovery"

#: Key type the Discovery Finder files the EDC Discovery under.
_BPN_TYPE = "bpn"


class MockIdentifier(BaseModel):
    """One identifier the mock BPN Discovery holds, and the BPN it belongs to."""

    type: str = Field(
        default="manufacturerPartId", description="Identifier type, e.g. 'manufacturerPartId'."
    )
    key: str = Field(min_length=1, description="The identifier, e.g. a manufacturer part ID.")
    bpn: str = Field(min_length=1, description="BPN the identifier is registered for.")


class MockDiscoveryParams(RequiredMockIdParams):
    """Input contract of ``mock/discovery``.

    ``mappings`` accepts either spelling tests already use: a plain
    BPN-to-endpoint object, or a list of ``{bpn, endpoint}`` entries.
    """

    mappings: dict[str, str] = Field(
        min_length=1,
        description="BPN to EDC endpoint mapping, or a list of {bpn, endpoint} entries.",
    )
    identifiers: list[MockIdentifier] = Field(
        default_factory=list,
        description=(
            "Identifiers the mock BPN Discovery holds, as {type, key, bpn} entries. "
            "Empty registers no BPN Discovery."
        ),
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
    """Output contract of ``mock/discovery``: where the mock services answer."""

    edc_discovery_url: str = Field(description="URL of the mock EDC Discovery.")
    bpn_discovery_url: str = Field(
        description="URL of the mock BPN Discovery; empty when no identifiers were given."
    )
    discovery_finder_url: str = Field(
        description="Search URL of the mock Discovery Finder, which names the other two."
    )


@step("mock/discovery")
class MockDiscoveryStep(BaseStep[MockDiscoveryParams, MockDiscoveryOutput]):
    """Register mock discovery services: EDC Discovery, BPN Discovery and the finder.

    A consumer step can then resolve a counter-party's DSP endpoint from its
    BPN, or a BPN from a part identifier, exactly as it would against the real
    services — the mock answers only for what it was asked about.
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
        identifiers = params.identifiers
        run = str(context.job.job_id)
        base_url = run_root(published_base_url(context), run)
        edc_discovery_url = f"{base_url}{_DISCOVERY_PATH}"
        bpn_discovery_url = f"{base_url}{_BPN_DISCOVERY_PATH}" if identifiers else ""
        identifier_types = {identifier.type for identifier in identifiers}

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
            # Mirrors the real EDC Discovery, which returns a bare JSON array.
            return MockResponse(status_code=200, body=result)

        def _search_bpns(req: MockRequest) -> MockResponse:
            filters = (req.body or {}).get("searchFilter", []) if isinstance(req.body, dict) else []
            wanted = {
                (entry.get("type"), key)
                for entry in filters
                if isinstance(entry, dict)
                for key in entry.get("keys", []) or []
            }
            found = [
                {
                    "type": identifier.type,
                    "key": identifier.key,
                    "value": identifier.bpn,
                    "resourceId": params.id,
                }
                for identifier in identifiers
                if (identifier.type, identifier.key) in wanted
            ]
            return MockResponse(status_code=200, body={"bpns": found})

        def _find(req: MockRequest) -> MockResponse:
            types = (req.body or {}).get("types", []) if isinstance(req.body, dict) else []
            offered = {_BPN_TYPE: edc_discovery_url} | dict.fromkeys(
                identifier_types, bpn_discovery_url
            )
            endpoints = [
                {
                    "type": kind,
                    "description": f"TestLab mock discovery for '{kind}'",
                    "endpointAddress": address,
                    "documentation": "",
                    "resourceId": params.id,
                }
                for kind, address in offered.items()
                if not types or kind in types
            ]
            return MockResponse(status_code=200, body={"endpoints": endpoints})

        register_mock(_DISCOVERY_PATH, "POST", _discover, run=run)
        register_mock(_FINDER_PATH, "POST", _find, run=run)
        if identifiers:
            register_mock(f"{_BPN_DISCOVERY_PATH}/search", "POST", _search_bpns, run=run)

        logger.info(
            "Registered mock discovery service '%s' with %d mappings and %d identifiers",
            params.id,
            len(bpn_to_endpoint),
            len(identifiers),
        )
        return StepOutput(
            value=MockDiscoveryOutput(
                edc_discovery_url=edc_discovery_url,
                bpn_discovery_url=bpn_discovery_url,
                discovery_finder_url=f"{base_url}{_FINDER_PATH}",
            )
        )

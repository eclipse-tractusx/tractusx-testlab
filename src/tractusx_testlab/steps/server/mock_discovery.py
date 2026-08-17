#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################

"""mock/discovery step — a BPN Discovery Finder mock.

Registers ``POST /api/administration/connectors/discovery`` (the EDC discovery
finder shape) so a consumer can resolve a counter-party's DSP endpoint from its
BPN, filtered to just the BPNs it asked about — mirroring the real service.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.server.mock_registry import MockRequest, MockResponse, register_mock
from tractusx_testlab.steps._contracts import NoOutput
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.steps.server._contracts import RequiredMockIdParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DISCOVERY_PATH = "/api/administration/connectors/discovery"


class MockDiscoveryParams(RequiredMockIdParams):
    """Input contract of ``mock/discovery``.

    ``mappings`` accepts either spelling scripts already use: a plain
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


@step("mock/discovery")
class MockDiscoveryStep(BaseStep[MockDiscoveryParams, NoOutput]):
    """Register a BPN Discovery Finder mock returning configured EDC endpoints.

    A consumer step can then resolve a counter-party's DSP endpoint from its BPN
    exactly as it would against the real service — the mock answers only for the
    BPNs it was asked about.
    """

    params_model = MockDiscoveryParams
    output_model = NoOutput

    async def execute(
        self, params: MockDiscoveryParams, context: StepContext, definition: StepDefinition,
    ) -> StepOutput[NoOutput]:
        bpn_to_endpoint = params.mappings

        def _discover(req: MockRequest) -> MockResponse:
            requested_bpns = req.body if isinstance(req.body, list) else (req.body or {}).get("bpns", [])
            if not requested_bpns:
                requested_bpns = list(bpn_to_endpoint.keys())
            result = [
                {"bpn": bpn, "connectorEndpoint": [bpn_to_endpoint[bpn]]}
                for bpn in requested_bpns
                if bpn in bpn_to_endpoint
            ]
            # Mirrors the real discovery finder, which returns a bare JSON array.
            return MockResponse(status_code=200, body=result)

        register_mock(_DISCOVERY_PATH, "POST", _discover)

        logger.info(
            "Registered mock discovery service '%s' with %d mappings",
            params.id, len(bpn_to_endpoint),
        )
        return StepOutput(value=NoOutput(None))

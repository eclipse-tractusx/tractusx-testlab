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

"""discovery/bpns_by_identifier — which business partners an identifier belongs to.

A data consumer often starts from a part, not a partner: a manufacturer part
ID on a delivery, a serial number in a recall. The dataspace's **BPN
Discovery** answers which BPNs registered it. The Discovery Finder names the
BPN Discovery for the identifier's type, and the SDK's ``BpnDiscoveryService``
asks both; the step builds it from ``infrastructure.engine.discovery`` and
reads what it answers.

The BPN it finds is what ``discovery/connectors_by_bpn`` takes next, so a
test can go from a part identifier to a connector and its protocol without a
partner ever being named.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition, StepExecutionError
from tractusx_testlab.steps.discovery._lookup import asked_url, build_services, call
from tractusx_testlab.steps.shared_models import StepParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

__all__ = [
    "MANUFACTURER_PART_ID",
    "BpnsByIdentifierOutput",
    "BpnsByIdentifierParams",
    "BpnsByIdentifierStep",
]

#: The identifier type a BPN Discovery is asked about when a test names none.
MANUFACTURER_PART_ID = "manufacturerPartId"


class BpnsByIdentifierParams(StepParams):
    """Input contract of ``discovery/bpns_by_identifier``."""

    keys: list[str] = Field(
        min_length=1,
        description="Identifiers to look up — one, or several of the same type.",
    )
    identifier_type: str = Field(
        default=MANUFACTURER_PART_ID,
        description="Type of the identifiers, as the BPN Discovery files them, e.g. 'manufacturerPartId'.",
    )
    discovery_finder_url: str = Field(
        default="",
        description=(
            "Discovery Finder search URL to ask instead of "
            "'infrastructure.engine.discovery.finder_url' — a mock's, most of all. The "
            "binding's technical user still signs the requests."
        ),
    )

    @field_validator("keys", mode="before")
    @classmethod
    def _one_key_is_a_list_of_one(cls, value: Any) -> Any:
        """Accept a single identifier as written, not only a list of them."""
        return [value] if isinstance(value, str) else value


class BpnsByIdentifierOutput(StepPayload):
    """Output contract of ``discovery/bpns_by_identifier``."""

    bpns: list[str] = Field(description="Every BPN the identifiers are registered for, sorted.")
    bpnl: str = Field(description="The first of them — the BPN to look a connector up for.")
    bpn_discovery_url: str = Field(
        description="BPN Discovery URL that was asked, as the finder answered it."
    )


@step("discovery/bpns_by_identifier")
class BpnsByIdentifierStep(BaseStep[BpnsByIdentifierParams, BpnsByIdentifierOutput]):
    """Look up the BPNs a part identifier is registered for.

    An identifier no BPN is registered for fails the step, naming the service
    asked: a test that goes on to look up a connector has nobody to look up.
    """

    params_model = BpnsByIdentifierParams
    output_model = BpnsByIdentifierOutput

    async def execute(
        self,
        params: BpnsByIdentifierParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[BpnsByIdentifierOutput]:
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
        discovery = services.bpns()

        found: Any = await call(
            self.step_type,
            f"the BPN Discovery behind the Discovery Finder at {finder_url}",
            discovery.find_bpns,
            params.keys,
            params.identifier_type,
        )
        bpn_discovery_url = asked_url(discovery.get_cache_status(), params.identifier_type)
        # The SDK answers a set's worth, in no order; sorted, a test can assert on it.
        bpns = sorted({bpn for bpn in found or [] if isinstance(bpn, str) and bpn})
        if not bpns:
            raise StepExecutionError(
                self.step_type,
                f"the BPN Discovery at {bpn_discovery_url or finder_url} holds no BPN for "
                f"{params.identifier_type} {', '.join(repr(key) for key in params.keys)}.",
            )

        logger.info(
            "%s %s belongs to %s", params.identifier_type, ", ".join(params.keys), ", ".join(bpns)
        )
        return StepOutput(
            value=BpnsByIdentifierOutput(
                bpns=bpns, bpnl=bpns[0], bpn_discovery_url=bpn_discovery_url
            )
        )

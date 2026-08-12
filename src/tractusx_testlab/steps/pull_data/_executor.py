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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Pull data executor — delegates to SDK's do_dsp() for the full DSP flow."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Optional

import requests
from pydantic import Field, field_validator

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.steps._contracts import (
    CounterPartyParams,
    DataplaneExports,
    FilterExpressionParams,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload
from tractusx_testlab.steps.pull_data._constants import (
    DEFAULT_MAX_WAIT,
    DEFAULT_POLL_INTERVAL,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


# -- Policy format helpers ---------------------------------------------------

_SIMPLIFIED_KEY_MAP: dict[str, str] = {
    "permissions": "permission",
    "prohibitions": "prohibition",
    "obligations": "obligation",
    "constraints": "constraint",
    "left_operand": "leftOperand",
    "right_operand": "rightOperand",
}


def _to_odrl_policy(value: object) -> object:
    """Recursively convert a simplified testlab policy dict to ODRL camelCase format.

    Maps snake_case keys and plural rule keys to the canonical ODRL names the
    SDK's ``DspTools.filter_assets_and_policies`` and ``_policies_match`` expect:
    - ``permissions``  → ``permission``
    - ``constraints``  → ``constraint``
    - ``left_operand`` → ``leftOperand``
    - ``right_operand``→ ``rightOperand``
    """
    if isinstance(value, dict):
        return {
            _SIMPLIFIED_KEY_MAP.get(k, k): _to_odrl_policy(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_to_odrl_policy(item) for item in value]
    return value


# -- Declared interface -------------------------------------------------------


class PullDataParams(CounterPartyParams, FilterExpressionParams):
    """What both pull-data shortcuts take.

    They run the whole DSP flow in one step, so they need everything the
    separate catalog, negotiation, and transfer steps would each have taken.
    """

    max_wait: float = Field(
        default=DEFAULT_MAX_WAIT,
        ge=0,
        description="Seconds to wait for the transfer to complete.",
    )
    poll_interval: float = Field(
        default=DEFAULT_POLL_INTERVAL,
        gt=0,
        description="Seconds between transfer-state polls.",
    )


class PullDataOutput(StepPayload):
    """Everything the DSP flow produced, from the catalog through to the token.

    The endpoint and token appear twice under different names because scripts
    written against either spelling still read this output.
    """

    endpoint: Optional[str] = Field(
        default=None, description="Data-plane URL the negotiated data is fetched from."
    )
    edr_token: str = Field(default="", description="Authorization token for that URL.")
    dataplane_url: str = Field(default="", description="Same as 'endpoint', as a string.")
    token_prefix: Optional[str] = Field(
        default=None,
        description="First characters of the token, safe to log or assert on.",
    )
    catalog: dict = Field(
        default_factory=dict, description="Catalog document the offer was taken from."
    )
    datasets: list[dict] = Field(
        default_factory=list, description="Dataset offers in that catalog."
    )
    asset_id: str = Field(default="", description="Asset ID of the first offer.")
    negotiation_id: Optional[str] = Field(
        default=None, description="ID of the negotiation the flow ran."
    )
    transfer_process_id: Optional[str] = Field(
        default=None, description="ID of the transfer process the flow ran."
    )


class PullDataByPolicyOutput(PullDataOutput):
    """Adds the two aliases ``pull_data_filtered_by_policy`` also publishes."""

    transfer_id: Optional[str] = Field(
        default=None, description="Same as 'transfer_process_id'."
    )
    agreement_id: Optional[str] = Field(
        default=None, description="Same as 'negotiation_id'."
    )


# -- Shared helpers -----------------------------------------------------------


async def _do_dsp_flow(
    context: "StepContext",
    params: PullDataParams,
    policies: Optional[list[dict]],
) -> tuple[PullDataOutput, HttpRequest, HttpResponse]:
    """Execute the full DSP flow via the SDK and describe what it produced."""
    consumer = context.get_consumer_service()
    filter_expression = params.sdk_filter_expression()
    counter_party_id = params.counter_party_id

    # Yield to event loop before blocking SDK call
    await asyncio.sleep(0)

    # Pre-fetch catalog to extract dataset metadata that tests may assert on.
    catalog: dict = {}
    datasets: list[dict] = []
    asset_id: str = ""
    try:
        catalog = consumer.get_catalog_with_filter(
            counter_party_id=counter_party_id,
            counter_party_address=params.counter_party_address,
            filter_expression=filter_expression,
        ) or {}
        raw_datasets = catalog.get("dataset", [])
        if isinstance(raw_datasets, dict):
            raw_datasets = [raw_datasets]
        datasets = raw_datasets or []
        asset_id = datasets[0].get("@id", "") if datasets else ""
    except (requests.RequestException, ConnectionError, TimeoutError) as exc:
        logger.debug("Pre-catalog fetch failed (will retry in do_dsp): %s", exc)

    catalog_participant_id = catalog.get("participantId")
    if catalog_participant_id and catalog_participant_id != counter_party_id:
        logger.info(
            "Resolved provider participantId from catalog: %s (config had: %s)",
            catalog_participant_id, counter_party_id,
        )
        counter_party_id = catalog_participant_id

    # Full DSP flow: use get_transfer_id + get_endpoint_with_token to expose
    # transfer_process_id as a distinct return value.
    transfer_process_id = consumer.get_transfer_id(
        counter_party_id=counter_party_id,
        counter_party_address=params.counter_party_address,
        filter_expression=filter_expression,
        policies=policies,
        max_wait=params.max_wait,
        poll_interval=params.poll_interval,
    )
    endpoint, token = consumer.get_endpoint_with_token(transfer_id=transfer_process_id)

    value = PullDataOutput(
        endpoint=endpoint,
        edr_token=token or "",
        dataplane_url=endpoint or "",
        token_prefix=token[:10] + "..." if token else None,
        catalog=catalog,
        datasets=datasets,
        asset_id=asset_id,
        negotiation_id=transfer_process_id,
        transfer_process_id=transfer_process_id,
    )
    request = HttpRequest(method="POST", url=params.counter_party_address)
    response = HttpResponse(
        status_code=200 if endpoint else 500,
        body={"endpoint": endpoint},
    )
    return value, request, response


def _dataplane_exports(value: PullDataOutput) -> DataplaneExports:
    """Publish the data-plane pair the dataplane step reads."""
    return DataplaneExports(data_address=value.endpoint, edr_token=value.edr_token or None)


# -- Steps --------------------------------------------------------------------


class PullDataFilteredParams(PullDataParams):
    """Input contract of ``connector/consumer/pull_data_filtered``."""

    policy: Optional[Any] = Field(
        default=None,
        description=(
            "Single policy the offer must satisfy, in ODRL or the testlab "
            "simplified form; omitted means the SDK picks the first offer."
        ),
    )

    def allowed_policies(self) -> Optional[list[dict]]:
        """The policy as the SDK's allow-list argument, or None for "any offer"."""
        if self.policy is None:
            return None
        converted = _to_odrl_policy(self.policy)
        return [converted] if isinstance(converted, dict) else converted


class ConnectorPullDataFiltered(BaseStep[PullDataFilteredParams, PullDataOutput]):
    """Run the full DSP flow in one step, optionally constrained to one policy.

    The ``policy:`` param accepts the testlab simplified format
    (``permissions``/``constraints``/snake_case keys) and is converted to ODRL
    camelCase, so the SDK's policy comparison can use it as an allow-list when
    filtering catalog assets.  With no policy the SDK takes the first offer.
    """

    params_model = PullDataFilteredParams
    output_model = PullDataOutput
    exports_model = DataplaneExports

    async def execute(
        self,
        params: PullDataFilteredParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[PullDataOutput]:
        value, request, response = await _do_dsp_flow(
            context, params, params.allowed_policies()
        )
        return StepOutput(
            value=value,
            request=request,
            response=response,
            exports=_dataplane_exports(value),
        )


class PullDataFilteredByPolicyParams(PullDataParams):
    """Input contract of ``connector/consumer/pull_data_filtered_by_policy``."""

    policies: list[dict] = Field(
        min_length=1,
        description="ODRL policies, any one of which the negotiated offer must satisfy.",
    )

    @field_validator("policies", mode="before")
    @classmethod
    def _one_policy_is_a_list_of_one(cls, value: Any) -> Any:
        """A single policy document is as valid as a list holding it."""
        return [value] if isinstance(value, dict) else value

    def allowed_policies(self) -> list[dict]:
        """The policies as the SDK's allow-list argument, in ODRL spelling."""
        return [_to_odrl_policy(policy) for policy in self.policies]


class ConnectorPullDataFilteredByPolicy(
    BaseStep[PullDataFilteredByPolicyParams, PullDataByPolicyOutput]
):
    """Run the full DSP flow, accepting an offer that matches any of several policies.

    Unlike ``pull_data_filtered`` (one optional, testlab-simplified ``policy``),
    this variant requires ``policies``.  Simplified snake_case keys are still
    normalised to ODRL camelCase, so either format is accepted.
    """

    params_model = PullDataFilteredByPolicyParams
    output_model = PullDataByPolicyOutput
    exports_model = DataplaneExports

    async def execute(
        self,
        params: PullDataFilteredByPolicyParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[PullDataByPolicyOutput]:
        value, request, response = await _do_dsp_flow(
            context, params, params.allowed_policies()
        )
        return StepOutput(
            value=PullDataByPolicyOutput(
                **value.model_dump(exclude_unset=True),
                transfer_id=value.transfer_process_id,
                agreement_id=value.negotiation_id,
            ),
            request=request,
            response=response,
            exports=_dataplane_exports(value),
        )

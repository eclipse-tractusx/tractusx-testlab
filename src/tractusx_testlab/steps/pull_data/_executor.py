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
from typing import TYPE_CHECKING

import requests

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinitionV2
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.steps.pull_data._constants import (
    DEFAULT_MAX_WAIT,
    DEFAULT_POLL_INTERVAL,
)
from tractusx_testlab.syntax.context_vars import DATAPLANE_ENDPOINT, EDR_TOKEN

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


# -- Shared helpers -----------------------------------------------------------


def _build_filter_expression(params: dict) -> list[dict]:
    """Build SDK-compatible filter expression from step params."""
    filters = params.get("filters", params.get("filter_expression", []))
    if isinstance(filters, dict):
        filters = [filters]
    return [
        {
            "operandLeft": f.get("operand_left", f.get("operandLeft", "")),
            "operator": f.get("operator", "="),
            "operandRight": f.get("operand_right", f.get("operandRight", "")),
        }
        for f in filters
        if isinstance(f, dict)
    ]


async def _do_dsp_flow(
    context: "StepContext",
    params: dict,
    filter_expression: list[dict],
    policies: list[dict] | dict | None,
) -> StepOutput:
    """Execute the full DSP flow via the SDK's do_dsp()."""
    if isinstance(policies, dict):
        policies = [policies]
    service_name: str | None = params.get("connector_service") or None
    consumer = context.get_consumer_service(service_name)
    counter_party_address = params.get("counter_party_address", "")
    counter_party_id = params.get("counter_party_id", "")
    max_wait = params.get("max_wait", DEFAULT_MAX_WAIT)
    poll_interval = params.get("poll_interval", DEFAULT_POLL_INTERVAL)

    # Yield to event loop before blocking SDK call
    await asyncio.sleep(0)

    # Pre-fetch catalog to extract dataset metadata that tests may assert on.
    catalog: dict = {}
    datasets: list = []
    asset_id: str = ""
    try:
        catalog = consumer.get_catalog_with_filter(
            counter_party_id=counter_party_id,
            counter_party_address=counter_party_address,
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
        counter_party_address=counter_party_address,
        filter_expression=filter_expression,
        policies=policies,
        max_wait=max_wait,
        poll_interval=poll_interval,
    )
    endpoint, token = consumer.get_endpoint_with_token(transfer_id=transfer_process_id)

    context.set_variable(DATAPLANE_ENDPOINT, endpoint)
    context.set_variable(EDR_TOKEN, token)

    return StepOutput(
        value={
            "endpoint": endpoint,
            "edr_token": token or "",
            "dataplane_url": endpoint or "",
            "token_prefix": token[:10] + "..." if token else None,
            "catalog": catalog,
            "datasets": datasets,
            "asset_id": asset_id,
            "negotiation_id": transfer_process_id,
            "transfer_process_id": transfer_process_id,
        },
        request=HttpRequest(method="POST", url=counter_party_address),
        response=HttpResponse(
            status_code=200 if endpoint else 500,
            body={"endpoint": endpoint},
        ),
    )


class ConnectorPullDataFiltered(BaseStep):
    """``connector/consumer/pull_data_filtered`` — full DSP flow with optional policy filter.

    The optional ``policy:`` param accepts the testlab simplified format
    (``permissions``/``constraints``/snake_case keys).  It is automatically
    converted to ODRL camelCase so the SDK's policy-comparison logic can use it
    as an allow-list when filtering catalog assets.

    When no policy is provided, ``policies=None`` is forwarded to ``do_dsp()``
    so the SDK auto-discovers the first available catalog policy.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2,
    ) -> StepOutput:
        normalized = dict(params)
        raw_policy = normalized.pop("policy", None)
        normalized.pop("policies", None)
        filter_expression = _build_filter_expression(normalized)

        policies: list[dict] | None = None
        if raw_policy is not None:
            odrl_policy = _to_odrl_policy(raw_policy)
            policies = [odrl_policy] if isinstance(odrl_policy, dict) else odrl_policy

        return await _do_dsp_flow(context, normalized, filter_expression, policies=policies)

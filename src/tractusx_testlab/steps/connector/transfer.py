#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Data transfer step — resolves the EDR data address for a negotiated contract."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.syntax.context_vars import (
    DATAPLANE_ENDPOINT,
    EDR_ENTRY,
    EDR_TOKEN,
    NEGOTIATION_ID,
    TRANSFER_ID,
)

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


@step("connector/consumer/transfer_data")
class TransferDataStep(BaseStep):
    async def execute(self, params: dict, context: "StepContext", definition: StepDefinition) -> StepOutput:
        consumer = context.get_consumer_service()
        url = f"{context.get_consumer_base_url()}/v3/transferprocesses"

        negotiation_id = params.get("negotiation_id") or context.get_variable(NEGOTIATION_ID)

        edr_entry = consumer.get_edr_entry(
            negotiation_id=negotiation_id,
            verify=params.get("verify"),
        )

        data_address_result = _resolve_data_address(edr_entry, consumer, context, params)
        endpoint, auth_token = _extract_endpoint_and_token(data_address_result)

        result_value = {
            "edr_entry": edr_entry,
            "data_address": endpoint,
            "edr_token": auth_token,
            "data_address_raw": data_address_result,
        }
        return StepOutput(
            value=result_value,
            request=HttpRequest(method="POST", url=url),
            response=HttpResponse(
                status_code=200 if edr_entry else 500,
                body=result_value,
            ),
        )


def _resolve_data_address(edr_entry: dict | None, consumer, context: "StepContext", params: dict) -> dict | None:
    """Resolve the EDR data address from the entry, storing variables in context."""
    if not edr_entry:
        return None

    transfer_process_id = edr_entry.get("transferProcessId") or edr_entry.get("@id")
    context.set_variable(TRANSFER_ID, transfer_process_id)
    context.set_variable(EDR_ENTRY, edr_entry)

    try:
        data_address_result = consumer.get_edr(
            transfer_id=transfer_process_id,
            verify=params.get("verify"),
        )
    except ConnectionError:
        logger.warning("Failed to retrieve EDR data address for transfer %s", transfer_process_id)
        return None

    if data_address_result:
        _store_data_address_vars(data_address_result, context)

    return data_address_result


def _store_data_address_vars(data_address_result: dict, context: "StepContext") -> None:
    """Store endpoint and auth token variables from a data address result."""
    endpoint = data_address_result.get("endpoint")
    auth_token = data_address_result.get("authorization") or data_address_result.get("authCode")
    if endpoint:
        context.set_variable("data_address", endpoint)
        context.set_variable(DATAPLANE_ENDPOINT, endpoint)
    if auth_token:
        context.set_variable(EDR_TOKEN, auth_token)
        context.set_variable("edr_token", auth_token)


def _extract_endpoint_and_token(data_address_result: dict | None) -> tuple[str | None, str | None]:
    """Extract endpoint and auth token from data address result."""
    if not data_address_result:
        return None, None
    endpoint = data_address_result.get("endpoint")
    auth_token = data_address_result.get("authorization") or data_address_result.get("authCode")
    return endpoint, auth_token

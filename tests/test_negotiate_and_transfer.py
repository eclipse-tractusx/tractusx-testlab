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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Contract tests for ``connector/consumer/negotiate`` and ``initiate_transfer``.

The two steps are tested together because they are one contract read from both
ends: what ``negotiate`` publishes is exactly what ``initiate_transfer`` reads.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from tractusx_testlab.steps.connector.dataplane import DataplaneCallParams
from tractusx_testlab.steps.connector.negotiate import NegotiateStep
from tractusx_testlab.steps.connector.transfer import InitiateTransferStep
from tractusx_testlab.syntax.context_vars import (
    AGREEMENT_ID,
    CATALOG_ASSET_ID,
    CATALOG_POLICY,
    DATA_ADDRESS,
    EDR_ENTRY,
    EDR_TOKEN,
    NEGOTIATION_ID,
    TRANSFER_ID,
)

_NEGOTIATION_ID = "neg-001"
_AGREEMENT_ID = "agr-001"
_TRANSFER_ID = "tp-001"
_ENDPOINT = "https://provider.example.com/api/public"
_TOKEN = "Bearer eyJhbGciOiJSUzI1NiJ9.test"


class _Response:
    """The bare shape of a ``requests.Response`` the SDK controllers hand back."""

    def __init__(self, status_code: int = 200, body: Optional[dict] = None) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no body")
        return self._body


class _StatefulController:
    """A management-API controller that walks through a list of states."""

    def __init__(self, *bodies: dict) -> None:
        self.bodies = list(bodies)
        self.reads = 0

    def get_by_id(self, oid: str, **kwargs: Any) -> _Response:
        self.reads += 1
        body = self.bodies[min(self.reads - 1, len(self.bodies) - 1)]
        return _Response(200, {"@id": oid, **body})


@pytest.fixture()
def definition() -> MagicMock:
    return MagicMock()


def _consumer(**attrs: Any) -> MagicMock:
    """A consumer service mock with no controller unless the test gives it one."""
    consumer = MagicMock()
    consumer.contract_negotiations = None
    consumer.transfer_processes = None
    consumer.dataspace_version = "jupiter"
    for name, value in attrs.items():
        setattr(consumer, name, value)
    return consumer


# ---------------------------------------------------------------------------
# connector/consumer/negotiate
# ---------------------------------------------------------------------------


class TestNegotiate:
    @pytest.mark.asyncio
    async def test_asset_id_and_policy_fall_back_to_the_catalog_step(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        """A script that ran ``query_catalog_by_asset_id`` first passes nothing."""
        consumer = _consumer()
        consumer.start_edr_negotiation.return_value = _NEGOTIATION_ID
        mock_context.get_consumer_service.return_value = consumer
        mock_context.set_variable(CATALOG_ASSET_ID, "urn:asset:1")
        mock_context.set_variable(CATALOG_POLICY, {"@type": "odrl:Set"})

        await NegotiateStep().invoke({}, mock_context, definition)

        call = consumer.start_edr_negotiation.call_args.kwargs
        assert (call["target"], call["policy"]) == ("urn:asset:1", {"@type": "odrl:Set"})

    @pytest.mark.asyncio
    async def test_polls_until_the_negotiation_finalises(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        """``agreement_id`` only exists once the negotiation is done."""
        negotiations = _StatefulController(
            {"state": "REQUESTED"},
            {"state": "FINALIZED", "contractAgreementId": _AGREEMENT_ID},
        )
        consumer = _consumer(contract_negotiations=negotiations)
        consumer.start_edr_negotiation.return_value = _NEGOTIATION_ID
        mock_context.get_consumer_service.return_value = consumer

        output = await NegotiateStep().invoke(
            {"poll_interval": 0.0}, mock_context, definition
        )

        assert negotiations.reads == 2
        assert output.value["state"] == "FINALIZED"
        assert output.value["agreement_id"] == _AGREEMENT_ID

    @pytest.mark.asyncio
    async def test_publishes_both_ids_for_the_transfer_step(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        consumer = _consumer(
            contract_negotiations=_StatefulController(
                {"state": "FINALIZED", "contractAgreementId": _AGREEMENT_ID}
            )
        )
        consumer.start_edr_negotiation.return_value = _NEGOTIATION_ID
        mock_context.get_consumer_service.return_value = consumer

        await NegotiateStep().invoke({"poll_interval": 0.0}, mock_context, definition)

        assert mock_context.variables[NEGOTIATION_ID] == _NEGOTIATION_ID
        assert mock_context.variables[AGREEMENT_ID] == _AGREEMENT_ID

    @pytest.mark.asyncio
    async def test_a_terminated_negotiation_is_reported_not_raised(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        """A refused negotiation is a result a script asserts on, not a crash."""
        consumer = _consumer(
            contract_negotiations=_StatefulController({"state": "TERMINATED"})
        )
        consumer.start_edr_negotiation.return_value = _NEGOTIATION_ID
        mock_context.get_consumer_service.return_value = consumer

        output = await NegotiateStep().invoke({"poll_interval": 0.0}, mock_context, definition)

        assert (output.value["state"], output.value["agreement_id"]) == ("TERMINATED", None)

    @pytest.mark.asyncio
    async def test_gives_up_when_the_negotiation_cannot_be_read(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        """An unreadable negotiation must not burn the whole wait window."""
        consumer = _consumer()
        consumer.start_edr_negotiation.return_value = _NEGOTIATION_ID
        mock_context.get_consumer_service.return_value = consumer

        output = await NegotiateStep().invoke({}, mock_context, definition)

        assert output.value["negotiation_id"] == _NEGOTIATION_ID
        assert output.value["state"] is None

    def test_target_is_no_longer_an_accepted_spelling(self) -> None:
        """C10 — the field is ``asset_id`` and nothing else.

        Under C47 the old spelling does not merely fail to bind: it is
        rejected, so a script still saying ``target:`` is told so rather than
        negotiating for nothing.
        """
        with pytest.raises(ValidationError, match="target"):
            NegotiateStep.params_model(target="urn:asset:1")


# ---------------------------------------------------------------------------
# connector/consumer/initiate_transfer — PULL
# ---------------------------------------------------------------------------


def _pull_consumer(**attrs: Any) -> MagicMock:
    consumer = _consumer(**attrs)
    consumer.get_edr_entry.return_value = {
        "@id": _TRANSFER_ID, "transferProcessId": _TRANSFER_ID
    }
    consumer.get_edr.return_value = {"endpoint": _ENDPOINT, "authorization": _TOKEN}
    return consumer


class TestInitiateTransferPull:
    @pytest.mark.asyncio
    async def test_resolves_the_negotiation_down_to_a_data_address(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        mock_context.get_consumer_service.return_value = _pull_consumer()
        mock_context.set_variable(NEGOTIATION_ID, _NEGOTIATION_ID)

        output = await InitiateTransferStep().invoke({}, mock_context, definition)

        assert output.value["data_address"] == _ENDPOINT
        assert output.value["edr_token"] == _TOKEN
        assert output.value["transfer_id"] == _TRANSFER_ID

    @pytest.mark.asyncio
    async def test_publishes_the_pair_the_dataplane_step_reads(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        """C34 — one name for the data-plane URL, and it is ``data_address``."""
        mock_context.get_consumer_service.return_value = _pull_consumer()
        mock_context.set_variable(NEGOTIATION_ID, _NEGOTIATION_ID)

        await InitiateTransferStep().invoke({}, mock_context, definition)

        assert mock_context.variables[DATA_ADDRESS] == _ENDPOINT
        assert mock_context.variables[EDR_TOKEN] == _TOKEN
        assert mock_context.variables[TRANSFER_ID] == _TRANSFER_ID
        assert EDR_ENTRY in mock_context.variables
        assert "dataplane_endpoint" not in mock_context.variables

    @pytest.mark.asyncio
    async def test_reports_the_transfer_state(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        consumer = _pull_consumer(
            transfer_processes=_StatefulController({"state": "STARTED"})
        )
        mock_context.get_consumer_service.return_value = consumer
        mock_context.set_variable(NEGOTIATION_ID, _NEGOTIATION_ID)

        output = await InitiateTransferStep().invoke({}, mock_context, definition)

        assert output.value["state"] == "STARTED"

    @pytest.mark.asyncio
    async def test_a_negotiation_without_an_edr_is_a_failed_response(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        consumer = _consumer()
        consumer.get_edr_entry.return_value = None
        mock_context.get_consumer_service.return_value = consumer

        output = await InitiateTransferStep().invoke({}, mock_context, definition)

        assert output.response.status_code == 500
        assert output.value["data_address"] is None


# ---------------------------------------------------------------------------
# connector/consumer/initiate_transfer — PUSH (C28)
# ---------------------------------------------------------------------------


_DESTINATION = {"type": "HttpData", "baseUrl": "https://sink.example.com/ingest"}


class TestInitiateTransferPush:
    @pytest.mark.asyncio
    async def test_posts_a_transfer_process_and_waits_for_it(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        transfers = _StatefulController({"state": "REQUESTED"}, {"state": "COMPLETED"})
        transfers.create = MagicMock(return_value=_Response(200, {"@id": _TRANSFER_ID}))
        consumer = _consumer(transfer_processes=transfers)
        mock_context.get_consumer_service.return_value = consumer
        mock_context.set_variable(AGREEMENT_ID, _AGREEMENT_ID)

        output = await InitiateTransferStep().invoke(
            {
                "transfer_type": "HttpData-PUSH",
                "data_destination": _DESTINATION,
                "counter_party_address": "https://provider.example.com/dsp",
                "poll_interval": 0.0,
            },
            mock_context,
            definition,
        )

        assert output.value["transfer_id"] == _TRANSFER_ID
        assert output.value["state"] == "COMPLETED"
        assert mock_context.variables[TRANSFER_ID] == _TRANSFER_ID

    @pytest.mark.asyncio
    async def test_the_request_carries_the_agreement_and_the_destination(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        transfers = _StatefulController({"state": "STARTED"})
        transfers.create = MagicMock(return_value=_Response(200, {"@id": _TRANSFER_ID}))
        mock_context.get_consumer_service.return_value = _consumer(transfer_processes=transfers)
        mock_context.set_variable(AGREEMENT_ID, _AGREEMENT_ID)

        await InitiateTransferStep().invoke(
            {
                "transfer_type": "AmazonS3-PUSH",
                "data_destination": _DESTINATION,
                "counter_party_address": "https://provider.example.com/dsp",
                "poll_interval": 0.0,
            },
            mock_context,
            definition,
        )

        sent = json.loads(transfers.create.call_args.args[0].to_data())
        assert sent["contractId"] == _AGREEMENT_ID
        assert sent["transferType"] == "AmazonS3-PUSH"
        assert sent["dataDestination"] == _DESTINATION

    @pytest.mark.asyncio
    async def test_a_push_without_a_destination_is_rejected(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        """Starting a PUSH with nowhere to push to fails later, at the provider."""
        with pytest.raises(ValueError, match="data_destination"):
            await InitiateTransferStep().invoke(
                {"transfer_type": "HttpData-PUSH"}, mock_context, definition
            )

    @pytest.mark.asyncio
    async def test_pull_is_what_happens_when_no_type_is_asked_for(
        self, mock_context: MagicMock, definition: MagicMock
    ) -> None:
        consumer = _pull_consumer()
        mock_context.get_consumer_service.return_value = consumer

        await InitiateTransferStep().invoke({}, mock_context, definition)

        consumer.get_edr_entry.assert_called_once()


# ---------------------------------------------------------------------------
# connector/dataplane/http_request — C18's engine half
# ---------------------------------------------------------------------------


class TestDataplaneCallParams:
    def test_the_canonical_spellings_bind(self) -> None:
        params = DataplaneCallParams(dataplane_url=_ENDPOINT, edr_token=_TOKEN)
        assert (params.dataplane_url, params.edr_token) == (_ENDPOINT, _TOKEN)

    @pytest.mark.parametrize("spelling", ["url", "endpoint"])
    def test_the_old_url_spellings_are_rejected(self, spelling: str) -> None:
        with pytest.raises(ValidationError, match=spelling):
            DataplaneCallParams(**{spelling: _ENDPOINT})

    def test_the_old_token_spelling_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="token"):
            DataplaneCallParams(token=_TOKEN)

    def test_a_data_address_object_resolves_to_its_endpoint(self) -> None:
        params = DataplaneCallParams(dataplane_url={"endpoint": _ENDPOINT})
        assert params.resolved_url(None) == _ENDPOINT

    def test_the_path_is_appended_without_doubling_the_separator(self) -> None:
        params = DataplaneCallParams(dataplane_url=_ENDPOINT + "/", path="/items")
        assert params.resolved_url(None) == _ENDPOINT + "/items"

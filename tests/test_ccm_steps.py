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

"""Unit tests for CCM-critical step executors."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.catalog_filter import QueryCatalogWithFiltersStep
from tractusx_testlab.steps.industry.notification import SendNotificationStep
from tractusx_testlab.steps.utility.json_extract import JsonPathExtractStep
from tractusx_testlab.steps.utility.uuid_gen import GenerateUuidStep


@pytest.fixture()
def definition() -> StepDefinition:
    """Minimal StepDefinition for test use."""
    return StepDefinition(uses="test_step", name="test")


# ---------------------------------------------------------------------------
# GenerateUuidStep
# ---------------------------------------------------------------------------


class TestGenerateUuidStep:
    """Tests for util/generate_uuid step."""

    @pytest.mark.asyncio
    async def test_generates_valid_uuid(self, mock_context: MagicMock, definition: StepDefinition) -> None:
        step = GenerateUuidStep()
        result = await step.invoke({}, mock_context, definition)
        parsed = uuid.UUID(result.value["generated_id"])
        assert parsed.version == 4

    @pytest.mark.asyncio
    async def test_prepends_prefix(self, mock_context: MagicMock, definition: StepDefinition) -> None:
        step = GenerateUuidStep()
        result = await step.invoke({"prefix": "urn:uuid:"}, mock_context, definition)
        assert result.value["generated_id"].startswith("urn:uuid:")
        uuid.UUID(result.value["generated_id"].removeprefix("urn:uuid:"))


# ---------------------------------------------------------------------------
# JsonPathExtractStep
# ---------------------------------------------------------------------------


class TestJsonPathExtractStep:
    """Tests for util/json_path_extract step."""

    @pytest.mark.asyncio
    async def test_extracts_nested_value(self, mock_context: MagicMock, definition: StepDefinition) -> None:
        mock_context.variables["catalog"] = {"dcat:dataset": [{"id": "ds-1"}]}
        step = JsonPathExtractStep()
        result = await step.invoke(
            {"input": "catalog", "path": "dcat:dataset.0.id"}, mock_context, definition
        )
        assert result.value == "ds-1"

    @pytest.mark.asyncio
    async def test_stores_in_variable(self, mock_context: MagicMock, definition: StepDefinition) -> None:
        mock_context.variables["data"] = {"key": "val"}
        step = JsonPathExtractStep()
        await step.invoke(
            {"input": "data", "path": "key", "store_in_variable": "extracted"},
            mock_context, definition,
        )
        assert mock_context.variables["extracted"] == "val"

    @pytest.mark.asyncio
    async def test_missing_input_raises_key_error(self, mock_context: MagicMock, definition: StepDefinition) -> None:
        step = JsonPathExtractStep()
        with pytest.raises(ValueError, match="input: Field required"):
            await step.invoke({"path": "x"}, mock_context, definition)

    @pytest.mark.asyncio
    async def test_nonexistent_variable_raises(self, mock_context: MagicMock, definition: StepDefinition) -> None:
        step = JsonPathExtractStep()
        with pytest.raises(KeyError, match="not found"):
            await step.invoke({"input": "missing", "path": "a"}, mock_context, definition)

    @pytest.mark.asyncio
    async def test_path_no_match_raises(self, mock_context: MagicMock, definition: StepDefinition) -> None:
        mock_context.variables["obj"] = {"a": 1}
        step = JsonPathExtractStep()
        with pytest.raises(KeyError):
            await step.invoke({"input": "obj", "path": "nonexistent"}, mock_context, definition)


# ---------------------------------------------------------------------------
# QueryCatalogWithFiltersStep
# ---------------------------------------------------------------------------


class TestQueryCatalogWithFiltersStep:
    """Tests for connector/consumer/query_catalog_with_filters step."""

    @pytest.mark.asyncio
    async def test_successful_catalog_query(
        self, mock_context: MagicMock, definition: StepDefinition
    ) -> None:
        catalog = {"dcat:dataset": [{"@id": "asset-1"}]}
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = catalog
        mock_context.get_consumer_service.return_value = consumer

        step = QueryCatalogWithFiltersStep()
        result = await step.invoke(
            {"counter_party_address": "http://provider:8080", "filters": []},
            mock_context, definition,
        )
        assert result.value["datasets"] == [{"@id": "asset-1"}]
        assert mock_context.variables["datasets"] == [{"@id": "asset-1"}]

    @pytest.mark.asyncio
    async def test_catalog_error_returns_none_value(
        self, mock_context: MagicMock, definition: StepDefinition
    ) -> None:
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = None
        mock_context.get_consumer_service.return_value = consumer

        step = QueryCatalogWithFiltersStep()
        result = await step.invoke(
            {"counter_party_address": "http://provider:8080"}, mock_context, definition,
        )
        assert result.value is None
        assert result.response.status_code == 500

    @pytest.mark.asyncio
    async def test_each_filter_is_translated_by_the_sdk(
        self, mock_context: MagicMock, definition: StepDefinition
    ) -> None:
        consumer = MagicMock()
        consumer.get_filter_expression.side_effect = lambda key, value, operator: {
            "operandLeft": key, "operator": operator, "operandRight": value,
        }
        consumer.get_catalog_with_filter.return_value = {"dcat:dataset": []}
        mock_context.get_consumer_service.return_value = consumer

        await QueryCatalogWithFiltersStep().invoke(
            {
                "counter_party_address": "http://provider:8080",
                "filters": [{"operand_left": "type", "operator": "=", "operand_right": "cert"}],
            },
            mock_context, definition,
        )
        assert consumer.get_catalog_with_filter.call_args.kwargs["filter_expression"] == [
            {"operandLeft": "type", "operator": "=", "operandRight": "cert"}
        ]

    @pytest.mark.asyncio
    async def test_no_filters_sends_an_empty_expression(
        self, mock_context: MagicMock, definition: StepDefinition
    ) -> None:
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = {"dcat:dataset": []}
        mock_context.get_consumer_service.return_value = consumer

        await QueryCatalogWithFiltersStep().invoke(
            {"counter_party_address": "http://provider:8080"}, mock_context, definition,
        )
        assert consumer.get_filter_expression.call_count == 0
        assert consumer.get_catalog_with_filter.call_args.kwargs["filter_expression"] == []


# ---------------------------------------------------------------------------
# SendNotificationStep
# ---------------------------------------------------------------------------


class TestSendNotificationStep:
    """Tests for notification/consumer/send step."""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_dataplane_direct_mode_posts(
        self, mock_client_cls: MagicMock, mock_context: MagicMock, definition: StepDefinition
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"ok": true}'
        mock_resp.json.return_value = {"ok": True}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        step = SendNotificationStep()
        result = await step.invoke(
            {"dataplane_url": "http://dp/notify", "edr_token": "tok", "content": {"msg": "hi"}},
            mock_context, definition,
        )
        assert result.value["status_code"] == 200
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    @patch("tractusx_sdk.industry.models.notifications.notification.Notification")
    async def test_sdk_mode_calls_service(
        self, mock_notif_cls: MagicMock, mock_context: MagicMock, definition: StepDefinition
    ) -> None:
        mock_notif_instance = MagicMock(to_data=MagicMock(return_value={}))
        mock_notif_cls.return_value = mock_notif_instance
        mock_service = MagicMock()
        mock_service.send_notification.return_value = {"status": "sent"}
        mock_context.get_notification_service = MagicMock(return_value=mock_service)

        step = SendNotificationStep()
        result = await step.invoke(
            {
                "notification": {"header": {"context": "cx", "senderBpn": "B1", "receiverBpn": "B2"}, "content": {}},
                "provider_bpn": "BPNL000000001",
                "provider_dsp_url": "http://provider/dsp",
            },
            mock_context, definition,
        )
        assert result.value == {"status": "sent"}
        mock_service.send_notification.assert_called_once()

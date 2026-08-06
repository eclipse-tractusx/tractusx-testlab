###############################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Integration tests: CCM step execution (UUID, JSON path, extract dataset, semantic schema)."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.steps.connector.extract import ExtractDatasetStep
from tractusx_testlab.steps.industry.semantic import ValidateSemanticSchemaStep
from tractusx_testlab.steps.utility.json_extract import JsonPathExtractStep
from tractusx_testlab.steps.utility.uuid_gen import GenerateUuidStep


def _make_mock_context(**variables: Any) -> MagicMock:
    """Create a mock StepContext with preset variables."""
    ctx = MagicMock()
    ctx.get_variable = MagicMock(side_effect=lambda name, default=None: variables.get(name, default))
    return ctx


def _make_step_definition(**overrides: Any) -> StepDefinitionV2:
    """Create a minimal StepDefinitionV2 for step execution tests."""
    uses = overrides.pop("type", "test")
    name = overrides.pop("name", "test-step")
    params = overrides.pop("params", {})
    overrides.pop("validate", None)
    return StepDefinitionV2(uses=uses, name=name, **{"with_": params} if params else {}, **overrides)


class TestGenerateUuidStep:
    @pytest.mark.asyncio
    async def test_generate_uuid_step_produces_valid_uuid(self) -> None:

        step_instance = GenerateUuidStep()
        ctx = _make_mock_context()
        definition = _make_step_definition(type="util/generate_uuid")

        output = await step_instance.invoke({}, ctx, definition)

        assert output.value is not None, "StepOutput must have a value"
        parsed = uuid.UUID(output.value["generated_id"], version=4)
        assert str(parsed) == output.value["generated_id"], "Output must be a valid UUID v4 string"

    @pytest.mark.asyncio
    async def test_generate_uuid_with_prefix(self) -> None:

        step_instance = GenerateUuidStep()
        ctx = _make_mock_context()
        definition = _make_step_definition(type="util/generate_uuid")

        output = await step_instance.invoke({"prefix": "urn:uuid:"}, ctx, definition)

        assert output.value["generated_id"].startswith("urn:uuid:"), "UUID should be prefixed"
        uuid_part = output.value["generated_id"][len("urn:uuid:"):]
        uuid.UUID(uuid_part, version=4)  # must not raise


class TestJsonPathExtractStep:
    @pytest.mark.asyncio
    async def test_json_path_extract_step(self) -> None:

        data = {"a": {"b": [{"id": "found-it"}]}}
        ctx = _make_mock_context(source_data=data)
        step_instance = JsonPathExtractStep()
        definition = _make_step_definition(type="util/json_path_extract")

        output = await step_instance.invoke(
            {"source": "source_data", "path": "a.b.0.id"}, ctx, definition,
        )

        assert output.value == "found-it"

    @pytest.mark.asyncio
    async def test_json_path_extract_missing_source_raises(self) -> None:

        ctx = _make_mock_context()
        step_instance = JsonPathExtractStep()
        definition = _make_step_definition(type="util/json_path_extract")

        with pytest.raises(KeyError, match="not found"):
            await step_instance.invoke(
                {"source": "nonexistent", "path": "any"}, ctx, definition,
            )


class TestExtractDatasetStep:
    @pytest.mark.asyncio
    async def test_extract_dataset_step(self) -> None:

        catalog = {
            "dcat:dataset": [
                {
                    "@id": "asset-ccm",
                    "edc:id": "asset-ccm-edc",
                    "dct:type": {"@id": "https://w3id.org/catenax/taxonomy#CCMAPI"},
                    "odrl:hasPolicy": {"@id": "offer-123"},
                },
                {
                    "@id": "asset-other",
                    "dct:type": {"@id": "https://w3id.org/catenax/taxonomy#OTHER"},
                },
            ]
        }
        ctx = _make_mock_context(catalog=catalog)
        step_instance = ExtractDatasetStep()
        definition = _make_step_definition(type="connector/consumer/extract_dataset")

        output = await step_instance.invoke(
            {"source": "catalog", "dct_type": "https://w3id.org/catenax/taxonomy#CCMAPI"},
            ctx, definition,
        )

        result = output.value
        assert len(result["datasets"]) == 1, "Should match exactly one dataset"
        assert result["asset_id"] == "asset-ccm-edc"
        assert result["offer_id"] == "offer-123"

    @pytest.mark.asyncio
    async def test_extract_dataset_no_match_returns_empty(self) -> None:

        catalog = {"dcat:dataset": []}
        ctx = _make_mock_context(catalog=catalog)
        step_instance = ExtractDatasetStep()
        definition = _make_step_definition(type="connector/consumer/extract_dataset")

        output = await step_instance.invoke(
            {"source": "catalog", "dct_type": "https://nonexistent"}, ctx, definition,
        )

        assert output.value["datasets"] == []
        assert output.value["offer_id"] is None
        assert output.value["asset_id"] is None


class TestValidateSemanticSchemaStep:
    @pytest.mark.asyncio
    async def test_validate_semantic_schema_valid_payload(self) -> None:

        payload = {"catenaXId": "urn:uuid:123", "childItems": []}
        ctx = _make_mock_context(payload=payload)
        step_instance = ValidateSemanticSchemaStep()
        definition = _make_step_definition(type="validate/semantic_schema")

        output = await step_instance.invoke(
            {"source": "payload", "schema_ref": "CX-0135"}, ctx, definition,
        )

        assert output.value["is_valid"] is True, "Valid payload should pass validation"
        assert output.value["missing_keys"] == []

    @pytest.mark.asyncio
    async def test_validate_semantic_schema_invalid_payload(self) -> None:

        payload = {"someOtherKey": "value"}
        ctx = _make_mock_context(payload=payload)
        step_instance = ValidateSemanticSchemaStep()
        definition = _make_step_definition(type="validate/semantic_schema")

        output = await step_instance.invoke(
            {"source": "payload", "schema_ref": "CX-0135"}, ctx, definition,
        )

        assert output.value["is_valid"] is False, "Invalid payload should fail validation"
        assert "catenaXId" in output.value["missing_keys"]
        assert "childItems" in output.value["missing_keys"]

    @pytest.mark.asyncio
    async def test_validate_semantic_schema_custom_keys(self) -> None:

        payload = {"myKey": "present"}
        ctx = _make_mock_context(payload=payload)
        step_instance = ValidateSemanticSchemaStep()
        definition = _make_step_definition(type="validate/semantic_schema")

        output = await step_instance.invoke(
            {"source": "payload", "schema_ref": "CUSTOM", "required_keys": ["myKey"]},
            ctx, definition,
        )

        assert output.value["is_valid"] is True
        assert output.value["schema_ref"] == "CUSTOM"

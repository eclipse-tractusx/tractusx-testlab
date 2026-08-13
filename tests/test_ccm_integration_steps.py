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

"""Integration tests: CCM step execution (UUID, JSON path, extract dataset)."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.extract import ExtractDatasetStep
from tractusx_testlab.steps.utility.json_extract import JsonPathExtractStep
from tractusx_testlab.steps.utility.uuid_gen import GenerateUuidStep


def _make_mock_context(**variables: Any) -> MagicMock:
    """Create a mock StepContext with preset variables."""
    ctx = MagicMock()
    ctx.get_variable = MagicMock(side_effect=lambda name, default=None: variables.get(name, default))
    return ctx


def _make_step_definition(**overrides: Any) -> StepDefinition:
    """Create a minimal StepDefinition for step execution tests."""
    uses = overrides.pop("type", "test")
    name = overrides.pop("name", "test-step")
    params = overrides.pop("params", {})
    overrides.pop("validate", None)
    return StepDefinition(uses=uses, name=name, **{"with_": params} if params else {}, **overrides)


class TestGenerateUuidStep:
    @pytest.mark.asyncio
    async def test_generate_uuid_step_produces_valid_uuid(self) -> None:

        step_instance = GenerateUuidStep()
        ctx = _make_mock_context()
        definition = _make_step_definition(type="util/generate_uuid")

        output = await step_instance.invoke({}, ctx, definition)

        assert output.value is not None, "StepOutput must have a value"
        parsed = uuid.UUID(output.value, version=4)
        assert str(parsed) == output.value, "Output must be a valid UUID v4 string"


class TestJsonPathExtractStep:
    @pytest.mark.asyncio
    async def test_json_path_extract_step(self) -> None:

        data = {"a": {"b": [{"id": "found-it"}]}}
        ctx = _make_mock_context(source_data=data)
        step_instance = JsonPathExtractStep()
        definition = _make_step_definition(type="util/json_path_extract")

        output = await step_instance.invoke(
            {"input": "source_data", "path": "a.b.0.id"}, ctx, definition,
        )

        assert output.value == "found-it"

    @pytest.mark.asyncio
    async def test_json_path_extract_missing_source_raises(self) -> None:

        ctx = _make_mock_context()
        step_instance = JsonPathExtractStep()
        definition = _make_step_definition(type="util/json_path_extract")

        with pytest.raises(KeyError, match="not found"):
            await step_instance.invoke(
                {"input": "nonexistent", "path": "any"}, ctx, definition,
            )


class TestExtractDatasetStep:
    @pytest.mark.asyncio
    async def test_extract_dataset_step(self) -> None:
        datasets = [
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
        ctx = _make_mock_context()
        step_instance = ExtractDatasetStep()
        definition = _make_step_definition(type="connector/consumer/extract_dataset")

        output = await step_instance.invoke(
            {
                "datasets": datasets,
                "dct_type": "https://w3id.org/catenax/taxonomy#CCMAPI",
            },
            ctx, definition,
        )

        result = output.value
        assert result["dataset"] == datasets[0]
        assert result["asset_id"] == "asset-ccm-edc"
        assert result["offer_id"] == "offer-123"

    @pytest.mark.asyncio
    async def test_extract_dataset_no_match_returns_empty(self) -> None:
        ctx = _make_mock_context()
        step_instance = ExtractDatasetStep()
        definition = _make_step_definition(type="connector/consumer/extract_dataset")

        output = await step_instance.invoke(
            {"datasets": [], "dct_type": "https://nonexistent"}, ctx, definition,
        )

        assert output.value["dataset"] is None
        assert output.value["offer_id"] is None
        assert output.value["asset_id"] is None

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

"""Tests for the declared interface of the connector/consumer/query_catalog steps."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition, StepExecutionError
from tractusx_testlab.steps.connector.catalog_query import (
    CatalogOutput,
    CatalogPayload,
    FilterExpression,
    QueryCatalogByAssetIdParams,
    QueryCatalogByAssetIdStep,
    QueryCatalogByBpnlStep,
    QueryCatalogParams,
    QueryCatalogStep,
)
from tractusx_testlab.steps.step_contract import StepOutput
from tractusx_testlab.syntax.context_vars import (
    CATALOG_ASSET_ID,
    CATALOG_POLICY,
)

#: Output field every catalog step returns its offers under, and therefore the
#: context variable it is published as.
_DATASETS = "datasets"

_DATASET = {"@id": "offer-abc", "odrl:hasPolicy": {"@id": "policy-1"}}
_CATALOG = {
    "@context": {"dcat": "http://www.w3.org/ns/dcat#"},
    "@id": "catalog-123",
    "@type": "dcat:Catalog",
    "dcat:dataset": [_DATASET],
    "dspace:participantId": "BPNL000000000001",
}


def _definition(uses: str) -> StepDefinition:
    return StepDefinition(id="q", uses=uses)


def _with_consumer(context: MagicMock, consumer: MagicMock) -> MagicMock:
    """Point the shared mock context at a stub consumer service."""
    context.dataspace.consumer.return_value = consumer
    context.dataspace.consumer_base_url.return_value = "http://consumer"
    return context


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class TestQueryCatalogParams:
    def test_canonical_names_are_accepted(self) -> None:
        params = QueryCatalogParams.model_validate(
            {"counter_party_address": "http://p/dsp", "counter_party_id": "BPNL01"}
        )
        assert (params.counter_party_address, params.counter_party_id) == (
            "http://p/dsp",
            "BPNL01",
        )

    def test_filters_are_parsed_into_expressions(self) -> None:
        params = QueryCatalogParams.model_validate(
            {"filters": [{"operand_left": "id", "operand_right": "a"}]}
        )
        assert params.filters[0].operand_left == "id"

    def test_filters_serialise_to_the_sdk_camel_case(self) -> None:
        params = QueryCatalogParams.model_validate(
            {"filters": [{"operand_left": "id", "operand_right": "a"}]}
        )
        assert params.filters[0].to_sdk() == {
            "operandLeft": "id",
            "operator": "=",
            "operandRight": "a",
        }

    def test_missing_required_asset_id_is_reported(self) -> None:
        with pytest.raises(ValueError, match="asset_id"):
            QueryCatalogByAssetIdStep.bind_params(
                {"counter_party_id": "BPNL01", "counter_party_address": "http://p"}
            )

    def test_bind_params_error_names_the_step(self) -> None:
        with pytest.raises(
            ValueError, match="Invalid parameters for step 'connector/consumer/query_catalog_by_asset_id'"
        ):
            QueryCatalogByAssetIdStep.bind_params({})


class TestFilterExpression:
    def test_snake_case_serialises_to_the_sdk_camel_case_shape(self) -> None:
        expression = FilterExpression.model_validate(
            {"operand_left": "id", "operator": "=", "operand_right": "asset-1"}
        )
        assert expression.to_sdk() == {
            "operandLeft": "id",
            "operator": "=",
            "operandRight": "asset-1",
        }

    def test_camel_case_input_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            FilterExpression.model_validate({"operandLeft": "id", "operandRight": "asset-1"})

    def test_operator_defaults_to_equality(self) -> None:
        assert FilterExpression.model_validate({"operand_left": "id"}).operator == "="


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class TestCatalogPayload:
    def test_provider_document_round_trips_unchanged(self) -> None:
        dumped = CatalogPayload.model_validate(_CATALOG).model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        assert dumped == _CATALOG

    def test_unknown_provider_keys_are_preserved(self) -> None:
        payload = CatalogPayload.model_validate({"vendor:extra": 1})
        assert payload.model_dump(by_alias=True, exclude_none=True)["vendor:extra"] == 1

    def test_plain_id_key_is_not_rewritten_as_json_ld_id(self) -> None:
        dumped = CatalogPayload.model_validate({"id": "plain"}).model_dump(
            by_alias=True, exclude_none=True
        )
        assert dumped == {"id": "plain"}

    def test_single_dataset_object_is_not_coerced_to_a_list(self) -> None:
        payload = CatalogPayload.model_validate({"dcat:dataset": _DATASET})
        assert payload.datasets == _DATASET

    def test_absent_json_ld_keys_are_not_invented(self) -> None:
        """A catalog without ``@type`` must not come back carrying ``"@type": null``."""
        output = QueryCatalogStep.bind_output(
            StepOutput(value=CatalogOutput(catalog={"@id": "c1", "dcat:dataset": []}))
        )
        assert output.value["catalog"] == {"@id": "c1", "dcat:dataset": []}

    def test_a_raw_catalog_is_not_accepted_as_the_step_value(self) -> None:
        """The document has to be bound to the contract, not just look like it."""
        with pytest.raises(TypeError, match="declares output_model=CatalogOutput"):
            QueryCatalogStep.bind_output(StepOutput(value={"@id": "c1"}))


class TestQueryCatalogStep:
    @pytest.mark.asyncio
    async def test_catalog_is_returned_as_the_step_value(self, mock_context: MagicMock) -> None:
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = _CATALOG
        output = await QueryCatalogStep().invoke(
            {"counter_party_address": "http://p/dsp", "counter_party_id": "BPNL01"},
            _with_consumer(mock_context, consumer),
            _definition("connector/consumer/query_catalog"),
        )
        assert output.value["catalog"] == _CATALOG
        assert output.value["datasets"] == [_DATASET]

    @pytest.mark.asyncio
    async def test_filters_reach_the_sdk_in_camel_case(self, mock_context: MagicMock) -> None:
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = _CATALOG
        await QueryCatalogStep().invoke(
            {"filters": [{"operand_left": "id", "operand_right": "asset-1"}]},
            _with_consumer(mock_context, consumer),
            _definition("connector/consumer/query_catalog"),
        )
        assert consumer.get_catalog_with_filter.call_args.kwargs["filter_expression"] == [
            {"operandLeft": "id", "operator": "=", "operandRight": "asset-1"}
        ]

    @pytest.mark.asyncio
    async def test_an_empty_catalog_fails_the_step(self, mock_context: MagicMock) -> None:
        """An empty catalog fails the step rather than reporting an invented 500.

        The status was never sent by the provider, and the runner records a
        step as PASSED unless it raises or an assertion hard-fails — so a
        provider that answered with nothing produced a passing conformance
        step.
        """
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = None
        with pytest.raises(StepExecutionError, match="no catalog"):
            await QueryCatalogStep().invoke(
                {},
                _with_consumer(mock_context, consumer),
                _definition("connector/consumer/query_catalog"),
            )


# ---------------------------------------------------------------------------
# Published outputs — every return output becomes a context variable
# ---------------------------------------------------------------------------


class TestQueryCatalogPublishedOutputs:
    @pytest.mark.asyncio
    async def test_datasets_are_published_to_the_context(self, mock_context: MagicMock) -> None:
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = _CATALOG
        ctx = _with_consumer(mock_context, consumer)
        await QueryCatalogStep().invoke({}, ctx, _definition("connector/consumer/query_catalog"))
        assert ctx.get_variable(_DATASETS) == [_DATASET]

    @pytest.mark.asyncio
    async def test_a_single_dataset_object_is_published_as_a_list(
        self, mock_context: MagicMock
    ) -> None:
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = {**_CATALOG, "dcat:dataset": _DATASET}
        ctx = _with_consumer(mock_context, consumer)
        await QueryCatalogStep().invoke({}, ctx, _definition("connector/consumer/query_catalog"))
        assert ctx.get_variable(_DATASETS) == [_DATASET]

    @pytest.mark.asyncio
    async def test_empty_catalog_publishes_nothing(self, mock_context: MagicMock) -> None:
        """A step that failed publishes nothing for a later step to read."""
        consumer = MagicMock()
        consumer.get_catalog_with_filter.return_value = None
        ctx = _with_consumer(mock_context, consumer)
        with pytest.raises(StepExecutionError):
            await QueryCatalogStep().invoke(
                {}, ctx, _definition("connector/consumer/query_catalog")
            )
        assert not ctx.has_variable(_DATASETS)


class TestQueryCatalogByAssetIdPublishedOutputs:
    @staticmethod
    def _params() -> dict:
        return {
            "counter_party_id": "BPNL01",
            "counter_party_address": "http://p/dsp",
            "asset_id": "asset-1",
        }

    @pytest.mark.asyncio
    async def test_matching_offer_is_published(self, mock_context: MagicMock, monkeypatch) -> None:
        from tractusx_testlab.steps.connector import catalog_query

        monkeypatch.setattr(
            catalog_query.DspTools,
            "filter_assets_and_policies",
            staticmethod(lambda catalog, allowed_policies: [("asset-1", {"@id": "policy-1"})]),
        )
        consumer = MagicMock()
        consumer.get_catalog_by_asset_id.return_value = _CATALOG
        ctx = _with_consumer(mock_context, consumer)
        await QueryCatalogByAssetIdStep().invoke(
            self._params(), ctx, _definition("connector/consumer/query_catalog_by_asset_id")
        )
        assert (ctx.get_variable(CATALOG_ASSET_ID), ctx.get_variable(CATALOG_POLICY)) == (
            "asset-1",
            {"@id": "policy-1"},
        )

    @pytest.mark.asyncio
    async def test_no_matching_offer_leaves_the_variables_unset(
        self, mock_context: MagicMock, monkeypatch
    ) -> None:
        from tractusx_testlab.steps.connector import catalog_query

        monkeypatch.setattr(
            catalog_query.DspTools,
            "filter_assets_and_policies",
            staticmethod(lambda catalog, allowed_policies: []),
        )
        consumer = MagicMock()
        consumer.get_catalog_by_asset_id.return_value = _CATALOG
        ctx = _with_consumer(mock_context, consumer)
        await QueryCatalogByAssetIdStep().invoke(
            self._params(), ctx, _definition("connector/consumer/query_catalog_by_asset_id")
        )
        assert not ctx.has_variable(CATALOG_ASSET_ID)

    @pytest.mark.asyncio
    async def test_malformed_catalog_does_not_fail_the_step(
        self, mock_context: MagicMock, monkeypatch
    ) -> None:
        from tractusx_testlab.steps.connector import catalog_query

        def _boom(catalog, allowed_policies):
            raise KeyError("odrl:hasPolicy")

        monkeypatch.setattr(
            catalog_query.DspTools, "filter_assets_and_policies", staticmethod(_boom)
        )
        consumer = MagicMock()
        consumer.get_catalog_by_asset_id.return_value = _CATALOG
        ctx = _with_consumer(mock_context, consumer)
        output = await QueryCatalogByAssetIdStep().invoke(
            self._params(), ctx, _definition("connector/consumer/query_catalog_by_asset_id")
        )
        assert output.response.status_code == 200
        assert not ctx.has_variable(CATALOG_ASSET_ID)


# ---------------------------------------------------------------------------
# The contract as documentation
# ---------------------------------------------------------------------------


class TestDeclaredContracts:
    @pytest.mark.parametrize(
        "step_cls",
        [QueryCatalogStep, QueryCatalogByAssetIdStep, QueryCatalogByBpnlStep],
    )
    def test_every_step_declares_inputs_and_outputs(self, step_cls: type) -> None:
        contract = step_cls.describe()
        assert contract.params_schema is not None
        assert contract.output_schema is not None

    def test_selected_offer_names_match_the_context_var_constants(self) -> None:
        properties = QueryCatalogByAssetIdStep.describe().output_schema["properties"]
        assert {CATALOG_ASSET_ID, CATALOG_POLICY} <= set(properties)

    def test_input_schema_documents_every_accepted_key(self) -> None:
        properties = QueryCatalogByAssetIdParams.model_json_schema()["properties"]
        assert set(properties) == {
            "counter_party_id",
            "counter_party_address",
            "asset_id",
            "expected_policies",
        }

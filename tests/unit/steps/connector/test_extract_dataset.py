################################################################################
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
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Unit tests for ``connector/consumer/extract_dataset``.

The step reads a dataset a counter-party wrote, so the same offer is asserted
on in both DSP spellings: prefixed (legacy connectors) and expanded (DSP
2025-1).  Which one arrives is the *provider's* generation, not the run's.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.steps.connector.extract import (
    ExtractDatasetParams,
    ExtractDatasetStep,
)

_DCT_TYPE = "cx-taxo:DigitalTwinRegistry"

#: The same offer as a legacy connector (EDC 0.8-0.10) serialises it.
_LEGACY_DATASET = {
    "@id": "dataset-1",
    "dct:type": {"@id": _DCT_TYPE},
    "edc:id": "asset-dtr",
    "odrl:hasPolicy": [{"@id": "offer-1"}],
}

#: The same offer as a DSP 2025-1 connector (EDC 0.11+) serialises it — the
#: ``@vocab`` context expands every term, so the prefixes are gone.
_DSP2025_DATASET = {
    "@id": "dataset-1",
    "dct:type": {"@id": _DCT_TYPE},
    "id": "asset-dtr",
    "hasPolicy": [{"@id": "offer-1"}],
}


async def _extract(datasets: list[dict], dct_type: str = _DCT_TYPE) -> MagicMock:
    step = ExtractDatasetStep()
    return await step.execute(
        ExtractDatasetParams(datasets=datasets, dct_type=dct_type),
        MagicMock(),
        MagicMock(),
    )


class TestExtractDatasetStep:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("dataset", [_LEGACY_DATASET, _DSP2025_DATASET])
    async def test_offer_and_asset_are_read_in_either_dsp_generation(self, dataset: dict) -> None:
        output = await _extract([dataset])
        assert output.value.dataset == dataset
        assert output.value.offer_id == "offer-1"
        assert output.value.asset_id == "asset-dtr"

    @pytest.mark.asyncio
    async def test_a_bare_policy_object_is_read_like_a_list_of_one(self) -> None:
        output = await _extract([{**_DSP2025_DATASET, "hasPolicy": {"@id": "offer-1"}}])
        assert output.value.offer_id == "offer-1"

    @pytest.mark.asyncio
    async def test_a_dataset_without_an_asset_property_falls_back_to_its_node_id(
        self,
    ) -> None:
        """Neither ``id`` nor ``edc:id``: the dataset's own ``@id`` is the asset."""
        output = await _extract([{"@id": "asset-dtr", "dct:type": {"@id": _DCT_TYPE}}])
        assert output.value.asset_id == "asset-dtr"

    @pytest.mark.asyncio
    async def test_no_dataset_of_that_type_yields_nothing_rather_than_a_wrong_one(
        self,
    ) -> None:
        output = await _extract([_DSP2025_DATASET], dct_type="cx-taxo:SomethingElse")
        assert output.value.dataset is None
        assert output.value.offer_id is None
        assert output.value.asset_id is None

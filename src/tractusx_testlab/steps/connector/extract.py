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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4).
## It was reviewed and tested by a human committer.

"""Dataset extraction step — filters catalog responses by dct:type."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DCT_TYPE_KEY = "dct:type"
_DCT_TYPE_ID_KEY = "@id"
_DATASET_KEY = "dcat:dataset"
_ODRL_HAS_POLICY = "odrl:hasPolicy"
_ASSET_ID_KEY = "edc:id"


def _find_datasets_by_type(catalog: dict, dct_type: str) -> list[dict]:
    """Filter catalog datasets matching the given dct:type @id."""
    datasets = catalog.get(_DATASET_KEY, [])
    if isinstance(datasets, dict):
        datasets = [datasets]

    matched: list[dict] = []
    for ds in datasets:
        ds_type = ds.get(_DCT_TYPE_KEY, {})
        is_match = (
            (isinstance(ds_type, dict) and ds_type.get(_DCT_TYPE_ID_KEY) == dct_type)
            or (isinstance(ds_type, str) and ds_type == dct_type)
        )
        if is_match:
            matched.append(ds)
    return matched


def _extract_offer_id(dataset: dict) -> str | None:
    """Extract the first offer/policy ID from a dataset."""
    policy = dataset.get(_ODRL_HAS_POLICY)
    if isinstance(policy, list) and policy:
        return policy[0].get(_DCT_TYPE_ID_KEY)
    if isinstance(policy, dict):
        return policy.get(_DCT_TYPE_ID_KEY)
    return None


@step("connector/consumer/extract_dataset")
class ExtractDatasetStep(BaseStep):
    """Extract matching datasets from a catalog response by dct:type.

    Params:
        source (str): Context variable name containing the catalog response.
        dct_type (str): The dct:type @id to filter by.

    Output:
        Dict with ``datasets``, ``offer_id``, and ``asset_id`` from the first match.
    """

    async def execute(
        self, params: dict, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput:
        source_name = params["source"]
        dct_type = params["dct_type"]

        catalog = context.get_variable(source_name)
        if catalog is None:
            raise KeyError(f"Context variable '{source_name}' not found")
        if not isinstance(catalog, dict):
            raise TypeError(f"Expected dict for catalog, got {type(catalog).__name__}")

        matched = _find_datasets_by_type(catalog, dct_type)
        logger.debug("Found %d dataset(s) matching dct:type '%s'", len(matched), dct_type)

        offer_id: str | None = None
        asset_id: str | None = None
        if matched:
            first = matched[0]
            offer_id = _extract_offer_id(first)
            asset_id = first.get(_ASSET_ID_KEY) or first.get("@id")

        return StepOutput(
            value={
                "datasets": matched,
                "offer_id": offer_id,
                "asset_id": asset_id,
            }
        )

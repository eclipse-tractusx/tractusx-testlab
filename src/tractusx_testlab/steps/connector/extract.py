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
from typing import TYPE_CHECKING, Optional

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import DATASET_KEY, StepParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DCT_TYPE_KEY = "dct:type"
_DCT_TYPE_ID_KEY = "@id"
_DATASET_KEY = DATASET_KEY
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


class ExtractDatasetParams(StepParams):
    """Input contract of ``connector/consumer/extract_dataset``.

    ``source`` names the variable a catalog step published — typically the
    :class:`~tractusx_testlab.steps._contracts.CatalogPayload` returned by
    ``query_catalog``.
    """

    source: str = Field(description="Context variable holding the catalog response.")
    dct_type: str = Field(description="The 'dct:type' @id datasets are filtered by.")


class ExtractDatasetOutput(StepPayload):
    """Output contract of ``connector/consumer/extract_dataset``.

    ``offer_id`` and ``asset_id`` describe the *first* match only; ``datasets``
    carries every one of them, so a script that expects several reads that.
    """

    datasets: list[dict] = Field(
        default_factory=list, description="Every dataset whose 'dct:type' matched."
    )
    offer_id: Optional[str] = Field(
        default=None, description="Policy/offer ID of the first match."
    )
    asset_id: Optional[str] = Field(default=None, description="Asset ID of the first match.")


@step("connector/consumer/extract_dataset")
class ExtractDatasetStep(BaseStep[ExtractDatasetParams, ExtractDatasetOutput]):
    """Extract matching datasets from a catalog response by ``dct:type``.

    A catalog offering exactly one dataset sends a bare object rather than a
    list; both forms are accepted here so a script does not have to care which
    one the provider chose.
    """

    params_model = ExtractDatasetParams
    output_model = ExtractDatasetOutput

    async def execute(
        self, params: ExtractDatasetParams, context: "StepContext", definition: StepDefinition
    ) -> StepOutput[ExtractDatasetOutput]:
        catalog = context.get_variable(params.source)
        if catalog is None:
            raise KeyError(f"Context variable '{params.source}' not found")
        if not isinstance(catalog, dict):
            raise TypeError(f"Expected dict for catalog, got {type(catalog).__name__}")

        matched = _find_datasets_by_type(catalog, params.dct_type)
        logger.debug("Found %d dataset(s) matching dct:type '%s'", len(matched), params.dct_type)

        offer_id: Optional[str] = None
        asset_id: Optional[str] = None
        if matched:
            first = matched[0]
            offer_id = _extract_offer_id(first)
            asset_id = first.get(_ASSET_ID_KEY) or first.get("@id")

        return StepOutput(
            value=ExtractDatasetOutput(
                datasets=matched, offer_id=offer_id, asset_id=asset_id
            )
        )

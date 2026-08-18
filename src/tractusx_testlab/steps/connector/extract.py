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
# License for the specific language governing permissions and limitations
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

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.shared_models import StepParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DCT_TYPE_KEY = "dct:type"
_DCT_TYPE_ID_KEY = "@id"
_ODRL_HAS_POLICY = "odrl:hasPolicy"
_ASSET_ID_KEY = "edc:id"


def _find_dataset_by_type(datasets: list[dict], dct_type: str) -> dict | None:
    """Return the first dataset matching the given dct:type @id."""
    for dataset in datasets:
        dataset_type = dataset.get(_DCT_TYPE_KEY, {})
        is_match = (
            (isinstance(dataset_type, dict) and dataset_type.get(_DCT_TYPE_ID_KEY) == dct_type)
            or (isinstance(dataset_type, str) and dataset_type == dct_type)
        )
        if is_match:
            return dataset
    return None


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

    ``datasets`` is wired directly from the output published by a catalog
    query step.
    """

    datasets: list[dict] = Field(description="Dataset offers returned by a catalog query.")
    dct_type: str = Field(description="The 'dct:type' @id used to select the dataset.")


class ExtractDatasetOutput(StepPayload):
    """Output contract of ``connector/consumer/extract_dataset``.

    The dataset and identifiers describe the first matching offer.
    """

    dataset: dict | None = Field(
        default=None, description="The first dataset whose 'dct:type' matched."
    )
    offer_id: str | None = Field(
        default=None, description="Policy/offer ID of the first match."
    )
    asset_id: str | None = Field(default=None, description="Asset ID of the first match.")


@step("connector/consumer/extract_dataset")
class ExtractDatasetStep(BaseStep[ExtractDatasetParams, ExtractDatasetOutput]):
    """Extract the first matching dataset from catalog offers by ``dct:type``."""

    params_model = ExtractDatasetParams
    output_model = ExtractDatasetOutput

    async def execute(
        self, params: ExtractDatasetParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ExtractDatasetOutput]:
        dataset = _find_dataset_by_type(params.datasets, params.dct_type)
        logger.debug(
            "Found dataset matching dct:type '%s': %s", params.dct_type, dataset is not None
        )

        offer_id: str | None = None
        asset_id: str | None = None
        if dataset is not None:
            offer_id = _extract_offer_id(dataset)
            asset_id = dataset.get(_ASSET_ID_KEY) or dataset.get("@id")

        return StepOutput(
            value=ExtractDatasetOutput(
                dataset=dataset, offer_id=offer_id, asset_id=asset_id
            )
        )

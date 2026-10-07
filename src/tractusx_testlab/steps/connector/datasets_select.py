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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""``connector/datasets/select`` — the operator picks the asset and the offer to negotiate.

A catalog filtered by type finds every offer of that type, and a system under
test is free to publish more than one: an asset per version, a stale one beside
the live one, one asset under several policies. A test that took the first
would negotiate whichever the connector listed first. This step is ``flow/select``
over the datasets a catalog query already returned: every asset and offer pair is
an option, shown with the asset's properties and the offer's policy, and the
chosen pair comes back ready for ``connector/consumer/negotiate``.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models.runtime.selection import SelectionOption
from tractusx_testlab.steps.dsp_keys import ASSET_ID_KEYS, ID_KEY, POLICY_KEYS, first_present
from tractusx_testlab.steps.flow.select import (
    SelectedBy,
    SelectionOutput,
    SelectionParams,
    SelectionStep,
)

#: What a dataset carries that is not a property of the asset: its ids, its
#: offers and where to fetch it from.
_NOT_PROPERTIES: frozenset[str] = frozenset(
    {*ASSET_ID_KEYS, "@type", "@context", *POLICY_KEYS, "distribution", "dcat:distribution"}
)


class SelectDatasetParams(SelectionParams):
    """Input contract of ``connector/datasets/select``."""

    datasets: list[dict[str, Any]] = Field(
        description=(
            "The datasets a catalog query returned, e.g. "
            "'${{ execution.<step>.datasets }}' of query_catalog_with_filters."
        ),
    )

    @field_validator("datasets", mode="before")
    @classmethod
    def _single_dataset(cls, value: Any) -> Any:
        return [value] if isinstance(value, dict) else value


class SelectDatasetOutput(SelectionOutput):
    """Output contract of ``connector/datasets/select``."""

    asset_id: str = Field(description="The id of the chosen asset.")
    offer_id: str | None = Field(default=None, description="The '@id' of the chosen offer.")
    policy: dict[str, Any] = Field(
        description=(
            "The chosen offer, as the provider wrote it — what 'negotiate' takes as 'policy'."
        )
    )
    dataset: dict[str, Any] = Field(description="The chosen asset's dataset, every offer included.")


def _offers(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    policies = first_present(dataset, POLICY_KEYS)
    if isinstance(policies, dict):
        return [policies]
    return [policy for policy in policies or [] if isinstance(policy, dict)]


def _pairs(
    params: SelectDatasetParams,
) -> list[tuple[SelectionOption, dict[str, Any], dict[str, Any]]]:
    """Every asset and offer pair the datasets hold, as an option, its dataset and its offer."""
    pairs: list[tuple[SelectionOption, dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for dataset in params.datasets:
        asset_id = first_present(dataset, ASSET_ID_KEYS)
        offers = _offers(dataset)
        if asset_id is None:
            continue
        properties = {key: value for key, value in dataset.items() if key not in _NOT_PROPERTIES}
        for index, offer in enumerate(offers, start=1):
            offer_id = offer.get(ID_KEY)
            option_id = f"{asset_id}::{offer_id or index}"
            if option_id in seen:
                option_id = f"{option_id}#{len(pairs) + 1}"
            seen.add(option_id)
            option = SelectionOption(
                id=option_id,
                label=str(asset_id),
                description=f"offer {index} of {len(offers)}"
                + (f": {offer_id}" if offer_id else ""),
                details={
                    "asset_id": str(asset_id),
                    "offer_id": offer_id,
                    "offer_index": index,
                    "offer_count": len(offers),
                    "properties": properties,
                    "policy": offer,
                },
            )
            pairs.append((option, dataset, offer))
    return pairs


@step("connector/datasets/select")
class SelectDatasetStep(SelectionStep[SelectDatasetParams, SelectDatasetOutput]):
    """Let the operator choose one asset and one of its offers out of a catalog's datasets.

    Does not query the catalog: give it the ``datasets`` of the catalog step
    before it. Each asset and offer pair is one option; a dataset with no offer
    cannot be negotiated and is left out. Read ``asset_id`` and ``policy`` to
    negotiate the pair.
    """

    params_model = SelectDatasetParams
    output_model = SelectDatasetOutput
    presentation = "catalog_offers"

    def options(self, params: SelectDatasetParams) -> list[SelectionOption]:
        return [option for option, _, _ in _pairs(params)]

    def chosen(
        self, params: SelectDatasetParams, option: SelectionOption, selected_by: SelectedBy
    ) -> SelectDatasetOutput:
        _, dataset, offer = next(pair for pair in _pairs(params) if pair[0].id == option.id)
        return SelectDatasetOutput(
            asset_id=option.details["asset_id"],
            offer_id=option.details["offer_id"],
            policy=offer,
            dataset=dataset,
            selected_by=selected_by,
        )

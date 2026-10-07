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

"""``connector/query_catalog/select_asset`` — the operator picks the asset a test is about.

A catalog query filtered by type finds every offer of that type, and a system
under test is free to publish more than one: a CCMAPI asset per version, or a
stale one beside the live one. A step that took the first would negotiate
whichever the connector listed first. This one reads the catalog, and when it
offers more than one asset it stops the run and puts them to the operator —
each with its properties and the policies it is offered under — and goes on
with the one chosen. The rest of the test negotiates that asset by its id.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import (
    HttpRequest,
    HttpResponse,
    StepDefinition,
    StepExecutionError,
    WaitAction,
)
from tractusx_testlab.models.runtime.selection import AssetSelection
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.connector._selection_wait import asset_id_of, await_choice, option_of
from tractusx_testlab.steps.counter_party import CounterParty, CounterPartyParams
from tractusx_testlab.steps.dsp_protocol import DspProtocolParams
from tractusx_testlab.steps.shared_models import FilterExpressionParams, as_dataset_list
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 300.0


class SelectAssetParams(CounterPartyParams, FilterExpressionParams, DspProtocolParams):
    """Input contract of ``connector/query_catalog/select_asset``."""

    asset_id: str | None = Field(
        default=None,
        description=(
            "The asset to take without asking, when the test already knows it — an operator "
            "input, say. It still has to be in the catalog."
        ),
    )
    ask_if_single: bool = Field(
        default=False,
        description="Ask even when the catalog offers only one asset, instead of taking it.",
    )
    timeout_s: float = Field(
        default=_DEFAULT_TIMEOUT_S,
        gt=0,
        description="Seconds to wait for the choice before failing.",
    )
    action: WaitAction | None = Field(
        default=None,
        description=(
            "What the choice is for, shown to the operator with the options: 'label', "
            "'description', 'recommendation' and 'fields'."
        ),
    )


class SelectAssetOutput(StepPayload):
    """The asset chosen, its dataset, and every dataset it was chosen from."""

    asset_id: str = Field(description="The id of the chosen asset.")
    dataset: dict = Field(description="The chosen asset's dataset, offers included.")
    datasets: list[dict] = Field(
        default_factory=list, description="Every dataset the catalog returned."
    )
    selected_by: Literal["operator", "input", "single"] = Field(
        description=(
            "How the asset was chosen: by the operator, by 'asset_id', or because it "
            "was the only one."
        )
    )


@step("connector/query_catalog/select_asset")
class SelectAssetStep(BaseStep[SelectAssetParams, SelectAssetOutput]):
    """Query a provider's catalog and let the operator choose one of its assets.

    No dataset fails the step. One is taken as it is, unless ``ask_if_single``.
    More than one are put to the operator — the run waits up to ``timeout_s``,
    the clock stopped while paused — and the chosen one is returned. Read
    ``asset_id`` to negotiate it, e.g. as an ``https://w3id.org/edc/v0.0.1/ns/id``
    filter of ``pull_data_filtered``.
    """

    params_model = SelectAssetParams
    output_model = SelectAssetOutput

    async def execute(
        self,
        params: SelectAssetParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[SelectAssetOutput]:
        consumer = context.dataspace.consumer()
        filter_expression = [
            consumer.get_filter_expression(
                key=entry.operand_left, value=entry.operand_right, operator=entry.operator
            )
            for entry in params.filters
        ]
        party = params.counter_party(context)
        catalog = await sdk_call.run(
            consumer.get_catalog_with_filter,
            counter_party_id=party.identity,
            counter_party_address=party.address,
            filter_expression=filter_expression,
            **params.sdk_protocol(),
        )
        url = f"{party.address}/catalog/request"
        request = HttpRequest(method="POST", url=url, body=params.model_dump(mode="json"))
        datasets = [entry for entry in as_dataset_list(catalog) if asset_id_of(entry)]
        if not datasets:
            raise StepExecutionError(
                self.step_type, f"the catalog from {url} offers no asset to choose from."
            )

        asset_id, selected_by = await self._choose(params, context, definition, datasets, party)
        dataset = next(entry for entry in datasets if asset_id_of(entry) == asset_id)
        return StepOutput(
            value=SelectAssetOutput(
                asset_id=asset_id, dataset=dataset, datasets=datasets, selected_by=selected_by
            ),
            request=request,
            response=HttpResponse(status_code=200, body=catalog),
        )

    async def _choose(
        self,
        params: SelectAssetParams,
        context: StepContext,
        definition: StepDefinition,
        datasets: list[dict],
        party: CounterParty,
    ) -> tuple[str, Literal["operator", "input", "single"]]:
        offered = [asset_id_of(entry) or "" for entry in datasets]
        if params.asset_id:
            if params.asset_id not in offered:
                raise StepExecutionError(
                    self.step_type,
                    f"asset '{params.asset_id}' is not in the catalog. Offered: "
                    f"{', '.join(offered)}.",
                )
            return params.asset_id, "input"
        if len(datasets) == 1 and not params.ask_if_single:
            return offered[0], "single"
        selection = AssetSelection(
            counter_party_address=party.address,
            counter_party_id=party.identity,
            options=[option_of(entry) for entry in datasets],
            action=params.action,
        )
        logger.info("Asking the operator to choose 1 of %d assets", len(datasets))
        asset_id, _ = await await_choice(context, definition, selection, params.timeout_s)
        return asset_id, "operator"

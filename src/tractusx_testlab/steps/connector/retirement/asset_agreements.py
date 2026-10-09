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
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-6).
## It was reviewed and tested by a human committer.

"""Discover and retire the engine provider agreements for one exact asset."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.retirement._operations import (
    RetirementReasonParams,
    RetirementResult,
    agreement_controller,
    query_agreements,
    retire,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class RetireAssetAgreementsParams(RetirementReasonParams):
    asset_id: str = Field(
        min_length=1, description="Exact engine asset ID whose provider agreements are retired."
    )


class RetireAssetAgreementsOutput(StepPayload):
    asset_id: str = Field(description="Exact engine asset selected for cleanup.")
    agreement_ids: list[str] = Field(
        description="All matching provider agreements discovered before retirement."
    )
    retirements: list[RetirementResult] = Field(
        description="Actual retirement outcome for each agreement."
    )
    status_code: int = Field(
        description="204 when all succeeded or none matched; first failure status, or 0 for a transport/invalid query failure."
    )
    error: str = Field(description="Query or transport diagnostic, empty when discovery succeeded.")


@step("connector/provider/retire_asset_agreements", dataspace_version="saturn")
class RetireAssetAgreementsStep(BaseStep[RetireAssetAgreementsParams, RetireAssetAgreementsOutput]):
    """Retire all engine provider agreements referencing one exact asset.

    Queries all pages before retiring any agreement, and checks each asset ID.
    A failed retirement does not prevent attempts for the remaining agreements.
    Use SOFT validations in teardown; retirement preserves agreement history.
    """

    params_model = RetireAssetAgreementsParams
    output_model = RetireAssetAgreementsOutput

    async def execute(
        self, params: RetireAssetAgreementsParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[RetireAssetAgreementsOutput]:
        controller = agreement_controller(context)
        ids, request, response, error = query_agreements(controller, params.asset_id)
        outcomes: list[RetirementResult] = []
        status = (
            (response.status_code if response is not None and response.status_code != 200 else 0)
            if error
            else 204
        )
        if not error:
            for agreement_id in ids:
                outcome, request, response = retire(controller, agreement_id, params.reason)
                outcomes.append(outcome)
                if status == 204 and outcome.status_code not in (200, 204):
                    status = outcome.status_code
        return StepOutput(
            value=RetireAssetAgreementsOutput(
                asset_id=params.asset_id,
                agreement_ids=ids,
                retirements=outcomes,
                status_code=status,
                error=error,
            ),
            request=request,
            response=response,
        )

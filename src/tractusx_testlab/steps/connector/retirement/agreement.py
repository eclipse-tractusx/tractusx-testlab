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

"""Retire one agreement on the engine's provider connector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.retirement._operations import (
    RetirementReasonParams,
    RetirementResult,
    agreement_controller,
    retire,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class RetireContractAgreementParams(RetirementReasonParams):
    agreement_id: str = Field(
        min_length=1, description="Agreement to retire on the engine provider connector."
    )


@step("connector/provider/retire_contract_agreement", dataspace_version="saturn")
class RetireContractAgreementStep(BaseStep[RetireContractAgreementParams, RetirementResult]):
    """Retire an engine provider agreement to prevent future transfers.

    Agreement history remains, so retirement does not guarantee asset deletion.
    Refused requests retain their status and body; use SOFT validations in teardown.
    No HTTP response is reported as status 0, never as successful retirement.
    """

    params_model = RetireContractAgreementParams
    output_model = RetirementResult

    async def execute(
        self,
        params: RetireContractAgreementParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[RetirementResult]:
        result, request, response = retire(
            agreement_controller(context), params.agreement_id, params.reason
        )
        return StepOutput(value=result, request=request, response=response)

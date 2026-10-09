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

"""SDK management calls shared by the retirement blocks.

SDK 0.8.2's agreement controller leaves query paths unversioned and inserts a
second slash in retirement paths. Use its adapter and models with explicit v3
paths until those convenience methods are corrected upstream.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic import Field
from requests import RequestException, Response
from tractusx_sdk.dataspace.controllers.connector.saturn.contract_agreement_controller import (
    ContractAgreementController,
)
from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory
from tractusx_sdk.dataspace.models.connector.saturn import ContractAgreementRetirementModel
from tractusx_sdk.dataspace.services.connector.base_connector_provider import (
    BaseConnectorProviderService,
)

from tractusx_testlab.models import HttpRequest, HttpResponse
from tractusx_testlab.steps.step_contract import StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

_AGREEMENTS = "/v3/contractagreements"
_PAGE_SIZE = 100
_MAX_PAGES = 1000
_EDC = "https://w3id.org/edc/v0.0.1/ns/"


class RetirementReasonParams(StepParams):
    reason: str = Field(
        default="TCK execution ended",
        min_length=1,
        description="Reason recorded in the provider's retirement history.",
    )


class RetirementResult(StepPayload):
    agreement_id: str = Field(description="Provider agreement targeted for retirement.")
    status_code: int = Field(description="Actual HTTP status; 0 means no HTTP response.")
    response_body: object | None = Field(
        default=None, description="Connector response or transport error."
    )


def agreement_controller(context: StepContext) -> ContractAgreementController:
    """Always use the engine connector; retirement must never reach the SUT."""
    provider = cast(BaseConnectorProviderService, context.dataspace.engine_provider())
    # SDK provider services expose the authenticated adapter, but only consumer
    # services expose contract_agreements. Bind the SDK controller to the engine
    # provider's adapter so retirement never uses a SUT or consumer binding.
    return ContractAgreementController(provider.dma_adapter)


def call(
    controller: ContractAgreementController, path: str, body: str
) -> tuple[HttpRequest, HttpResponse | None, str]:
    """Preserve refused calls and transport errors for soft author validations."""
    request = HttpRequest(
        method="POST", url=controller.adapter.base_url.rstrip("/") + path, body=body
    )
    try:
        response: Response | None = controller.adapter.post(url=path, data=body, timeout=30)
    except RequestException as exc:
        return request, None, f"{type(exc).__name__}: {exc}"
    if response is None:
        return request, None, "Connector returned no HTTP response"
    try:
        response_body = response.json() if response.content else None
    except ValueError:
        response_body = response.text
    return request, HttpResponse(status_code=response.status_code, body=response_body), ""


def retire(
    controller: ContractAgreementController, agreement_id: str, reason: str
) -> tuple[RetirementResult, HttpRequest, HttpResponse | None]:
    model = ContractAgreementRetirementModel(agreement_id=agreement_id, reason=reason)
    request, response, error = call(controller, _AGREEMENTS + "/retirements", model.to_data())
    result = RetirementResult(
        agreement_id=agreement_id,
        status_code=response.status_code if response is not None else 0,
        response_body=response.body if response is not None else error,
    )
    return result, request, response


def query_agreements(
    controller: ContractAgreementController, asset_id: str
) -> tuple[list[str], HttpRequest, HttpResponse | None, str]:
    """Collect every matching ID before mutations; reject partial inventories."""
    ids: list[str] = []
    for page_number in range(_MAX_PAGES):
        spec = ModelFactory.get_queryspec_model(
            dataspace_version="saturn",
            offset=page_number * _PAGE_SIZE,
            limit=_PAGE_SIZE,
            filter_expression=[
                {"operandLeft": "assetId", "operator": "=", "operandRight": asset_id}
            ],
        )
        request, response, error = call(controller, _AGREEMENTS + "/request", spec.to_data())
        if response is None or response.status_code != 200:
            return [], request, response, error or "Agreement query was refused"
        page = response.body
        if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
            return [], request, response, "Agreement query must return a JSON array of objects"
        for row in page:
            # Check exact asset ownership even if the backend ignores the query.
            if _field(row, "assetId") != asset_id:
                continue
            agreement_id = row.get("@id") or _field(row, "id")
            if not isinstance(agreement_id, str) or not agreement_id:
                return [], request, response, "Matching agreement is missing its ID"
            if agreement_id not in ids:
                ids.append(agreement_id)
        if len(page) < _PAGE_SIZE:
            return ids, request, response, ""
    return [], request, response, "Agreement query exceeded the pagination limit"


def _field(row: dict, name: str) -> object:
    return row.get(name, row.get(f"edc:{name}", row.get(_EDC + name)))

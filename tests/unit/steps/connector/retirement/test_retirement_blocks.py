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

"""Retirement uses real SDK models and adapters against a transport double."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from requests import PreparedRequest, Response, Timeout
from tractusx_sdk.dataspace.services.connector.service_factory import ServiceFactory

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.retirement.agreement import RetireContractAgreementStep
from tractusx_testlab.steps.connector.retirement.asset_agreements import RetireAssetAgreementsStep

ASSET = "cx-test-suite:run-a:asset"
EDC = "https://w3id.org/edc/v0.0.1/ns/"


@pytest.fixture()
def transport():
    provider = ServiceFactory.get_connector_provider_service(
        dataspace_version="saturn",
        base_url="https://engine",
        dma_path="/management",
        headers={"X-Api-Key": "secret"},
    )
    ctx = MagicMock()
    ctx.dataspace.engine_provider.return_value = provider
    requests: list[PreparedRequest] = []
    replies: list[tuple[int, object] | Exception | None] = []

    def send(request: PreparedRequest, **kwargs: object) -> Response | None:
        requests.append(request)
        assert kwargs["timeout"] == 30
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if reply is None:
            return None
        status, body = reply
        response = Response()
        response.status_code = status
        response._content = json.dumps(body).encode() if body is not None else b""
        response.request = request
        return response

    provider.dma_adapter.session.send = send
    return ctx, requests, replies


async def invoke(step, ctx, **params):
    return await step.invoke(
        raw_params=params, context=ctx, definition=StepDefinition(uses=step.step_type)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [204, 409, 404, 403, 500])
async def test_single_retirement_preserves_real_status_and_body(transport, status):
    ctx, requests, replies = transport
    body = [{"type": "ObjectConflict", "message": "already retired"}] if status != 204 else None
    replies.append((status, body))
    output = await invoke(
        RetireContractAgreementStep(), ctx, agreement_id="agreement-a", reason="Test ended"
    )
    assert output.value == {
        "agreement_id": "agreement-a",
        "status_code": status,
        "response_body": body,
    }
    assert requests[0].method == "POST"
    assert requests[0].url == "https://engine/management/v3/contractagreements/retirements"
    assert requests[0].headers["Content-Type"] == "application/json"
    assert requests[0].headers["X-Api-Key"] == "secret"
    assert json.loads(requests[0].body) == {
        "@context": {"edc": EDC, "tx": "https://w3id.org/tractusx/v0.0.1/ns/"},
        "edc:agreementId": "agreement-a",
        "tx:reason": "Test ended",
    }
    assert output.response.status_code == status
    ctx.dataspace.provider.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [Timeout("connector unavailable"), None])
async def test_no_http_response_is_not_successful_retirement(transport, failure):
    ctx, _, replies = transport
    replies.append(failure)
    output = await invoke(RetireContractAgreementStep(), ctx, agreement_id="agreement-a")
    assert output.value["status_code"] == 0
    assert output.value["response_body"]
    assert output.response is None


@pytest.mark.asyncio
async def test_asset_query_paginates_filters_exactly_deduplicates_and_continues_on_refusal(
    transport,
):
    ctx, requests, replies = transport
    replies.extend(
        [
            (
                200,
                [{"@id": "agreement-a", "assetId": ASSET}] * 99
                + [{"@id": "foreign", "assetId": ASSET + "-other"}],
            ),
            (
                200,
                [
                    {"@id": "agreement-b", "edc:assetId": ASSET},
                    {"@id": "agreement-c", EDC + "assetId": ASSET},
                ],
            ),
            (409, {"message": "already retired"}),
            (204, None),
            (500, {"message": "unavailable"}),
        ]
    )
    output = await invoke(RetireAssetAgreementsStep(), ctx, asset_id=ASSET)
    assert output.value["agreement_ids"] == ["agreement-a", "agreement-b", "agreement-c"]
    assert [row["status_code"] for row in output.value["retirements"]] == [409, 204, 500]
    assert output.value["status_code"] == 409
    specs = [json.loads(request.body) for request in requests[:2]]
    assert [spec["offset"] for spec in specs] == [0, 100]
    assert specs[0]["filterExpression"] == [
        {"operandLeft": "assetId", "operator": "=", "operandRight": ASSET}
    ]
    assert all(
        request.url.startswith("https://engine/management/v3/contractagreements/")
        for request in requests
    )
    ctx.dataspace.provider.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply, expected_status",
    [
        ((404, {}), 404),
        ((500, {}), 500),
        ((200, {}), 0),
        ((200, [{"assetId": ASSET}]), 0),
        (Timeout("offline"), 0),
    ],
)
async def test_failed_discovery_returns_diagnostic_and_never_retires_partial_inventory(
    transport, reply, expected_status
):
    ctx, requests, replies = transport
    replies.extend([(200, [{"@id": "agreement-a", "assetId": ASSET}] * 100), reply])
    output = await invoke(RetireAssetAgreementsStep(), ctx, asset_id=ASSET)
    assert len(requests) == 2
    assert all(request.url.endswith("/request") for request in requests)
    assert output.value["status_code"] == expected_status
    assert output.value["error"]
    assert output.value["agreement_ids"] == []
    assert output.value["retirements"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], [{"@id": "foreign", "assetId": ASSET + "-other"}]])
async def test_empty_or_unrelated_agreements_need_no_mutations(transport, rows):
    ctx, requests, replies = transport
    replies.append((200, rows))
    output = await invoke(RetireAssetAgreementsStep(), ctx, asset_id=ASSET)
    assert output.value["status_code"] == 204
    assert output.value["retirements"] == []
    assert len(requests) == 1


@pytest.mark.parametrize(
    "step, field",
    [
        (RetireContractAgreementStep, "agreement_id"),
        (RetireAssetAgreementsStep, "asset_id"),
    ],
)
def test_block_contract_rejects_missing_ids_and_other_dataspace_versions(step, field):
    assert StepRegistry.get(step.step_type, "saturn") is step
    assert StepRegistry.get(step.step_type, "jupiter") is None
    with pytest.raises(ValidationError):
        step.params_model.model_validate({field: ""})
    with pytest.raises(ValidationError):
        step.params_model.model_validate({})

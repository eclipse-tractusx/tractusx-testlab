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

"""Raw HTTP provisioning cannot publish other apps' engine resources."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tractusx_testlab.models import AuthoringError, StepDefinition
from tractusx_testlab.steps.http.request import HttpRequestParams, HttpRequestStep

PREFIX = "cx-test-suite:run-a:"
BASE = "https://engine/management/"


@pytest.fixture()
def context():
    return SimpleNamespace(
        resource_prefix=PREFIX,
        config=SimpleNamespace(credential_release=frozenset(), default_timeout_s=30),
        infrastructure=SimpleNamespace(
            engine=SimpleNamespace(connector=SimpleNamespace(management_url=BASE))
        ),
    )


async def send(context, collection, body, base=BASE):
    return await HttpRequestStep().execute(
        HttpRequestParams(method="POST", url=base + "v3/" + collection, body=body),
        context,
        StepDefinition(uses="http/http_request"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("collection", ["assets", "policydefinitions", "contractdefinitions"])
@pytest.mark.parametrize("resource_id", ["other-app-resource", "cx-test-suite:run-a-asset"])
async def test_unscoped_creation_is_rejected_before_sending(context, collection, resource_id):
    with (
        patch(
            "tractusx_testlab.steps.http.request.http_client.request", new_callable=AsyncMock
        ) as request,
        pytest.raises(AuthoringError, match="execution.resource_prefix"),
    ):
        await send(context, collection, {"@id": resource_id})
    request.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("as_json_string", [False, True])
async def test_scoped_raw_asset_body_is_sent_unchanged(context, as_json_string):
    body = {"@id": PREFIX + "asset", "properties": {"dct:type": "CCMAPI"}}
    if as_json_string:
        body = json.dumps(body)
    response = httpx.Response(
        200, json={"@id": PREFIX + "asset"}, request=httpx.Request("POST", BASE + "v3/assets")
    )
    with patch(
        "tractusx_testlab.steps.http.request.http_client.request", AsyncMock(return_value=response)
    ) as request:
        await send(context, "assets", body)
    sent = request.call_args.kwargs
    assert sent["content"] == body.encode() if as_json_string else sent["json"] == body


@pytest.mark.asyncio
@pytest.mark.parametrize("selector_prefix", [None, "cx-test-suite:run-a-", PREFIX])
async def test_raw_contract_definition_requires_a_scoped_selector(context, selector_prefix):
    body = {
        "@id": PREFIX + "offer",
        "accessPolicyId": PREFIX + "access",
        "contractPolicyId": PREFIX + "usage",
        "assetsSelector": [{"operandLeft": "dct:type", "operator": "=", "operandRight": "CCMAPI"}],
    }
    if selector_prefix:
        body["assetsSelector"].append(
            {"operandLeft": "id", "operator": "like", "operandRight": selector_prefix + "%"}
        )
    response = httpx.Response(
        200,
        json={"@id": body["@id"]},
        request=httpx.Request("POST", BASE + "v3/contractdefinitions"),
    )
    with patch(
        "tractusx_testlab.steps.http.request.http_client.request", AsyncMock(return_value=response)
    ) as request:
        if selector_prefix == PREFIX:
            await send(context, "contractdefinitions", body)
            request.assert_awaited_once()
        else:
            with pytest.raises(AuthoringError, match="selectors"):
                await send(context, "contractdefinitions", body)
            request.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_http_endpoints_keep_their_authored_body(context):
    body = {"@id": "sut-resource"}
    response = httpx.Response(
        200, json=body, request=httpx.Request("POST", "https://sut/v3/assets")
    )
    with patch(
        "tractusx_testlab.steps.http.request.http_client.request", AsyncMock(return_value=response)
    ) as request:
        await send(context, "assets", body, base="https://sut/")
    assert request.call_args.kwargs["json"] == body

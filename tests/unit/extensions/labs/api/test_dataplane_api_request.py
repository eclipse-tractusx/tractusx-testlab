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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""labs/connector/dataplane/api_request — built from the document, sent through the data plane."""

from __future__ import annotations

import pytest

from tests.unit.extensions.labs.api.api_harness import context, json_answer, record, run, serve
from tests.unit.openapi.documents import shop
from tractusx_testlab.extensions.labs.steps.api.calls.dataplane_api_request import (
    DataplaneApiRequestStep,
)
from tractusx_testlab.models import StepStatus
from tractusx_testlab.steps.connector._edr import edr_token

USES = "labs/connector/dataplane/api_request"
_DATAPLANE = "https://dp.provider.test/api/public"
_TOKEN = "edr-token-value-0123456789abcdef"
_OK = {"id": "m", "share": 1}


def _ctx():
    ctx = context(shop())
    ctx.set_variable("dataplane_url", _DATAPLANE)
    ctx.set_variable("edr_token", edr_token(_TOKEN, _DATAPLANE))
    return ctx


async def _call(with_: dict, ctx=None, **extra):
    params = {
        "api": "${{ env.apis.shop }}",
        "operation": "getMaterial",
        "path_params": {"id": "7"},
        **with_,
    }
    return await run(DataplaneApiRequestStep, USES, params, ctx or _ctx(), **extra)


@pytest.mark.asyncio
async def test_the_dataplane_and_token_come_from_the_context(monkeypatch) -> None:
    seen = serve(monkeypatch, json_answer(200, _OK, **{"X-Rate-Limit": "1"}))
    result = await _call({"query": {"lang": "en"}})
    assert result.status == StepStatus.PASSED, result.error
    assert str(seen[0].url) == f"{_DATAPLANE}/materials/7?lang=en"
    assert seen[0].headers["authorization"] == _TOKEN
    assert _TOKEN not in record(result)


@pytest.mark.asyncio
async def test_the_servers_base_path_is_stripped_from_a_path_that_repeats_it(monkeypatch) -> None:
    seen = serve(monkeypatch, json_answer(200, _OK))
    await _call({"base_path": "/materials"})
    assert str(seen[0].url) == f"{_DATAPLANE}/7"


@pytest.mark.asyncio
async def test_an_empty_token_sends_none(monkeypatch) -> None:
    seen = serve(monkeypatch, json_answer(403, {"error": "no"}))
    result = await _call({"edr_token": "", "expect": 403})
    assert seen[0].headers.get("authorization", "") == ""
    assert result.status == StepStatus.PASSED, result.error


@pytest.mark.asyncio
async def test_given_values_win_over_the_context(monkeypatch) -> None:
    seen = serve(monkeypatch, json_answer(200, _OK))
    other = "https://other-dp.test/public"
    await _call({"dataplane_url": {"endpoint": other}, "edr_token": "plain-token-xyz"})
    assert str(seen[0].url) == f"{other}/materials/7"
    assert seen[0].headers["authorization"] == "plain-token-xyz"


@pytest.mark.asyncio
async def test_no_dataplane_anywhere_is_refused(monkeypatch) -> None:
    seen = serve(monkeypatch, json_answer(200, _OK))
    result = await _call({}, context(shop()))
    assert "no dataplane_url" in result.error and seen == []


@pytest.mark.asyncio
async def test_a_data_plane_refusal_is_classified_by_the_check(monkeypatch) -> None:
    serve(monkeypatch, json_answer(403, {"error": "denied"}))
    result = await _call(
        {}, validate=[{"uses": "labs/validate/api_response", "with": {"data_plane": True}}]
    )
    check = result.assertions[0]
    assert not check.passed and check.actual[0]["check"] == "data_plane"
    assert "refused the EDR token" in check.message

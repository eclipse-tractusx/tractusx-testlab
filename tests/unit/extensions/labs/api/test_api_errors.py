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

"""labs/validate/api_errors — the test's error answers, judged together."""

from __future__ import annotations

import pytest

from tests.unit.extensions.labs.api.api_harness import context, json_answer, run, serve
from tests.unit.openapi.documents import shop
from tractusx_testlab.extensions.labs.steps.api.calls.api_request import ApiRequestStep
from tractusx_testlab.extensions.labs.steps.api.verdicts.api_errors import ApiErrorsStep
from tractusx_testlab.models import StepStatus

USES = "labs/validate/api_errors"


async def _provoke(monkeypatch, ctx, status: int, body: object, expect=None) -> None:
    serve(monkeypatch, json_answer(status, body))
    params = {"api": "${{ env.apis.shop }}", "operation": "getMaterial", "path_params": {"id": "1"}}
    if expect is not None:
        params["expect"] = expect
    await run(ApiRequestStep, "labs/http/api_request", params, ctx)


@pytest.mark.asyncio
async def test_consistent_discreet_errors_pass(monkeypatch) -> None:
    ctx = context(shop())
    await _provoke(monkeypatch, ctx, 404, {"title": "Not found", "status": 404}, expect=404)
    await _provoke(monkeypatch, ctx, 200, {"id": "m", "share": 1})
    result = await run(ApiErrorsStep, USES, {}, ctx)
    assert result.status == StepStatus.PASSED, result.assertions
    assert result.output == {"passed": True, "checked": 2, "errors": 1, "problems": []}


@pytest.mark.asyncio
async def test_each_check_fails_on_its_own(monkeypatch) -> None:
    ctx = context(shop())
    await _provoke(monkeypatch, ctx, 400, {"msg": "bad"}, expect=400)
    await _provoke(
        monkeypatch,
        ctx,
        500,
        {"title": "t", "status": 500, "detail": "at 10.0.0.12"},
        expect="error",
    )
    result = await run(ApiErrorsStep, USES, {}, ctx)
    failed = {c.assertion.name: c.passed for c in result.assertions}
    assert result.status == StepStatus.FAILED
    assert failed == {"format": False, "leaks": False, "client_errors": False}


@pytest.mark.asyncio
async def test_given_responses_are_judged_against_a_given_schema() -> None:
    responses = [
        {"status_code": 409, "response_body": {"code": "C"}, "response_headers": {}},
        {"status_code": 422, "response_body": {"title": "t"}, "response_headers": {}},
    ]
    result = await run(
        ApiErrorsStep,
        USES,
        {"responses": responses, "schema": {"type": "object", "required": ["code"]}},
        context(),
    )
    assert [(p["status"], p["keyword"]) for p in result.output["problems"]] == [(422, "required")]


@pytest.mark.asyncio
async def test_problem_json_is_checked_when_asked() -> None:
    responses = [
        {
            "status_code": 404,
            "response_body": {"title": "x"},
            "response_headers": {"Content-Type": "application/json"},
        }
    ]
    result = await run(
        ApiErrorsStep, USES, {"responses": responses, "format": "problem+json"}, context()
    )
    assert "not application/problem+json" in result.output["problems"][0]["message"]


@pytest.mark.asyncio
async def test_the_journal_belongs_to_one_test(monkeypatch) -> None:
    ctx = context(shop())
    await _provoke(monkeypatch, ctx, 404, {"bad": 1})
    ctx.steps.clear()
    result = await run(ApiErrorsStep, USES, {}, ctx)
    assert result.output["checked"] == 0


@pytest.mark.asyncio
async def test_steps_narrows_the_answers_to_those_steps(monkeypatch) -> None:
    ctx = context(shop())
    await _provoke(monkeypatch, ctx, 400, {"msg": "bad"})  # step id "call"
    result = await run(ApiErrorsStep, USES, {"steps": ["another"]}, ctx)
    assert result.output["checked"] == 0
    result = await run(ApiErrorsStep, USES, {"steps": ["call"]}, ctx)
    assert result.output["checked"] == 1 and not result.output["passed"]

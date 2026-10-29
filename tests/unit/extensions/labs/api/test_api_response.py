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

"""labs/validate/api_response as a step: the last answer, or one given, checked."""

from __future__ import annotations

import pytest

from tests.unit.extensions.labs.api.api_harness import context, run
from tests.unit.openapi.documents import shop
from tractusx_testlab.extensions.labs.steps.api.verdicts.api_response import ApiResponseCheckStep
from tractusx_testlab.models import StepStatus

USES = "labs/validate/api_response"
_REF = {"api": "shop", "id": "getMaterial", "method": "GET", "path": "/materials/{id}"}


def _answer(status: int = 200, body: object = None, **headers: str) -> dict:
    return {
        "status_code": status,
        "response_body": {"id": "m", "share": 1} if body is None else body,
        "response_headers": {"Content-Type": "application/json", "X-Rate-Limit": "1", **headers},
        "operation": _REF,
    }


@pytest.mark.asyncio
async def test_the_answer_the_last_call_published_is_checked() -> None:
    ctx = context(shop())
    for name, value in _answer().items():
        ctx.set_variable(name, value)
    result = await run(ApiResponseCheckStep, USES, {}, ctx)
    assert result.status == StepStatus.PASSED, result.error
    assert result.output == {
        "passed": True,
        "status_code": 200,
        "operation": "getMaterial",
        "problems": [],
    }
    assert {c.assertion.name for c in result.assertions} >= {"status", "body", "headers"}


@pytest.mark.asyncio
async def test_a_failing_check_fails_the_step_and_keeps_the_verdict() -> None:
    result = await run(
        ApiResponseCheckStep, USES, {"input": _answer(body={"id": 3})}, context(shop())
    )
    assert result.status == StepStatus.FAILED
    assert result.output["passed"] is False
    failed = [c.assertion.name for c in result.assertions if not c.passed]
    assert failed == ["body"]


@pytest.mark.asyncio
async def test_api_and_operation_may_be_given_for_any_answer() -> None:
    answer = {**_answer(), "operation": None}
    result = await run(
        ApiResponseCheckStep,
        USES,
        {
            "input": answer,
            "api": "${{ env.apis.shop }}",
            "operation": "GET /materials/{id}",
            "expect": 200,
        },
        context(shop()),
    )
    assert result.status == StepStatus.PASSED, result.error


@pytest.mark.asyncio
async def test_an_answer_with_nothing_to_check_it_against_is_an_authoring_error() -> None:
    answer = {**_answer(), "operation": None}
    result = await run(ApiResponseCheckStep, USES, {"input": answer}, context(shop()))
    assert result.error_code == "API_RESPONSE_UNCHECKABLE"


@pytest.mark.asyncio
async def test_something_that_is_not_an_answer_is_refused() -> None:
    result = await run(ApiResponseCheckStep, USES, {"input": {"x": 1}}, context(shop()))
    assert "not an API answer" in result.error

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

"""labs/http/api_request — the request built from the document, sent to base_url only."""

from __future__ import annotations

import httpx
import pytest

from tests.unit.extensions.labs.api.api_harness import context, json_answer, record, run, serve
from tests.unit.openapi.documents import ich, shop
from tractusx_testlab.extensions.labs.steps.api.calls.api_request import ApiRequestStep
from tractusx_testlab.models import StepStatus

USES = "labs/http/api_request"
API = "${{ env.apis.shop }}"
_MATERIAL = {"id": "m-1", "share": 0.5}
_HEADERS = {"X-Rate-Limit": "10"}


async def _call(with_: dict, ctx=None, **extra):
    return await run(ApiRequestStep, USES, {"api": API, **with_}, ctx or context(shop()), **extra)


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_the_operation_is_called_and_its_answer_returned(self, monkeypatch) -> None:
        seen = serve(monkeypatch, json_answer(200, _MATERIAL, **_HEADERS))
        result = await _call(
            {"operation": "getMaterial", "path_params": {"id": "a/b"}, "query": {"lang": "de"}}
        )
        assert result.status == StepStatus.PASSED, result.error
        assert str(seen[0].url) == "https://shop.example/api/v1/materials/a%2Fb?lang=de"
        assert seen[0].headers["accept"] == "application/json"
        assert result.output["status_code"] == 200
        assert result.output["response_body"] == _MATERIAL
        assert result.output["operation"] == {
            "api": "shop",
            "id": "getMaterial",
            "method": "GET",
            "path": "/materials/{id}",
        }

    @pytest.mark.asyncio
    async def test_the_operation_may_be_named_by_method_and_path(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(200, [], **_HEADERS))
        result = await _call({"operation": "GET /materials", "query": {"limit": 1}})
        assert result.status == StepStatus.PASSED, result.error

    @pytest.mark.asyncio
    async def test_a_given_base_url_replaces_the_documents_server(self, monkeypatch) -> None:
        seen = serve(monkeypatch, json_answer(200, "up"))
        await _call({"operation": "health", "base_url": "http://sut.test:8080/x/"})
        assert str(seen[0].url) == "http://sut.test:8080/x/health"

    @pytest.mark.asyncio
    async def test_the_record_names_the_api_never_the_document(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(200, _MATERIAL, **_HEADERS))
        result = await _call({"operation": "getMaterial", "path_params": {"id": "1"}})
        written = record(result)
        assert '"id": "shop"' in written and "components" not in written
        assert result.inputs["api"]["api_document"]["id"] == "shop"

    @pytest.mark.asyncio
    async def test_the_answer_is_noted_for_api_errors(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(404, {"title": "t", "status": 404}))
        ctx = context(shop())
        await _call({"operation": "getMaterial", "path_params": {"id": "1"}}, ctx)
        (noted,) = ctx.steps.api_exchanges.entries()
        assert (noted.api, noted.operation, noted.status) == ("shop", "getMaterial", 404)


class TestRefusals:
    @pytest.mark.asyncio
    async def test_a_missing_required_parameter_fails_before_anything_is_sent(
        self, monkeypatch
    ) -> None:
        seen = serve(monkeypatch, json_answer(200, {}))
        result = await _call({"operation": "getMaterial"})
        assert result.status == StepStatus.FAILED
        assert result.error_code == "API_REQUEST_INVALID"
        assert "path parameter 'id' is required" in result.error
        assert seen == []

    @pytest.mark.asyncio
    async def test_an_unknown_operation_names_the_closest(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(200, {}))
        result = await _call({"operation": "getMaterials"})
        assert "did you mean 'getMaterial'" in result.error

    @pytest.mark.asyncio
    async def test_a_header_with_a_line_break_is_refused(self, monkeypatch) -> None:
        seen = serve(monkeypatch, json_answer(200, {}))
        result = await _call({"operation": "health", "headers": {"X-Api-Key": "k\r\nX-Evil: 1"}})
        assert result.error_code == "API_REQUEST_INVALID" and seen == []

    @pytest.mark.asyncio
    async def test_api_must_be_an_api_file(self, monkeypatch) -> None:
        result = await run(
            ApiRequestStep, USES, {"api": {"openapi": "3.1.0"}, "operation": "x"}, context()
        )
        assert "env.apis" in result.error

    @pytest.mark.asyncio
    async def test_no_base_url_and_no_absolute_server_is_refused(self, monkeypatch) -> None:
        result = await run(
            ApiRequestStep,
            USES,
            {"api": "${{ env.apis.ich }}", "operation": "check_health_health_get"},
            context(ich()),
        )
        assert "no base_url" in result.error

    @pytest.mark.asyncio
    async def test_an_unexpected_status_fails_the_step(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(500, {"title": "t", "status": 500}))
        result = await _call(
            {"operation": "getMaterial", "path_params": {"id": "1"}, "expect": "success"}
        )
        assert result.error_code == "API_STATUS_UNEXPECTED"
        assert "answered 500, expected success" in result.error

    @pytest.mark.asyncio
    async def test_an_expected_error_passes(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(404, {"title": "t", "status": 404}))
        result = await _call(
            {"operation": "getMaterial", "path_params": {"id": "1"}, "expect": "4xx"}
        )
        assert result.status == StepStatus.PASSED, result.error

    @pytest.mark.asyncio
    async def test_an_expectation_that_is_none_of_the_forms_is_refused(self) -> None:
        result = await _call({"operation": "health", "expect": "sometimes"})
        assert "expect must be" in result.error

    @pytest.mark.asyncio
    async def test_a_redirect_is_answered_not_followed(self, monkeypatch) -> None:
        seen = serve(
            monkeypatch, lambda _r: httpx.Response(302, headers={"Location": "https://evil.test/"})
        )
        result = await _call({"operation": "health"})
        assert len(seen) == 1 and result.output["status_code"] == 302

    @pytest.mark.asyncio
    async def test_an_oversized_answer_is_refused_unread(self, monkeypatch) -> None:
        from tractusx_testlab.extensions.labs.steps.api.calls import call_contract

        monkeypatch.setattr(call_contract, "MAX_RESPONSE_BYTES", 1024)
        monkeypatch.setattr(
            "tractusx_testlab.extensions.labs.steps.api.calls.api_request.MAX_RESPONSE_BYTES", 1024
        )
        serve(monkeypatch, lambda _r: httpx.Response(200, content=b"x" * 5000))
        result = await _call({"operation": "health"})
        assert result.error_code == "RESPONSE_TOO_LARGE"


class TestValidateUnder:
    @pytest.mark.asyncio
    async def test_api_response_reads_the_steps_own_answer(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(200, _MATERIAL, **_HEADERS))
        result = await _call(
            {"operation": "getMaterial", "path_params": {"id": "1"}},
            validate=[{"uses": "labs/validate/api_response"}],
        )
        assert result.status == StepStatus.PASSED
        assert result.assertions[0].passed

    @pytest.mark.asyncio
    async def test_api_response_fails_the_step_with_every_problem(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(200, {"share": "x"}))
        result = await _call(
            {"operation": "getMaterial", "path_params": {"id": "1"}},
            validate=[{"uses": "labs/validate/api_response"}],
        )
        check = result.assertions[0]
        assert result.status == StepStatus.FAILED and not check.passed
        assert {p["check"] for p in check.actual} == {"body", "headers"}
        assert "#/components/schemas/Material/properties/share/type" in check.message

    @pytest.mark.asyncio
    async def test_an_api_handed_to_the_check_is_recorded_by_summary(self, monkeypatch) -> None:
        serve(monkeypatch, json_answer(200, _MATERIAL, **_HEADERS))
        result = await _call(
            {"operation": "getMaterial", "path_params": {"id": "1"}},
            validate=[{"uses": "labs/validate/api_response", "with": {"api": API, "expect": 200}}],
        )
        assert result.assertions[0].passed
        assert "components" not in record(result)

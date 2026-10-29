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

"""labs/http/api_sweep — safe by default, bounded, and one row per operation."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from tests.unit.extensions.labs.api.api_harness import context, run, serve
from tests.unit.openapi.documents import shop
from tractusx_testlab.extensions.labs.steps.api.calls.api_sweep import ApiSweepStep
from tractusx_testlab.models import StepStatus

USES = "labs/http/api_sweep"
API = "${{ env.apis.shop }}"


def _shop_server(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/health"):
        return httpx.Response(200, text="up", headers={"Content-Type": "text/plain"})
    if path.endswith("/materials"):
        if request.method == "POST":
            return httpx.Response(201)
        return httpx.Response(200, json=[{"id": "m", "share": 1}])
    if request.method == "DELETE":
        return httpx.Response(204)
    return httpx.Response(200, json={"id": "m", "share": 1}, headers={"X-Rate-Limit": "5"})


def _rows(result) -> dict[str, tuple]:
    return {row["operation"]: (row["verdict"], row["status"]) for row in result.output["results"]}


@pytest.mark.asyncio
async def test_reads_are_called_and_checked_writes_left_alone(monkeypatch) -> None:
    seen = serve(monkeypatch, _shop_server)
    result = await run(
        ApiSweepStep, USES, {"api": API, "params": {"id": "m", "limit": 2}}, context(shop())
    )
    assert result.status == StepStatus.PASSED, result.output
    assert _rows(result) == {
        "getMaterial": ("passed", 200),
        "listMaterials": ("passed", 200),
        "health": ("passed", 200),
    }
    assert {r.method for r in seen} == {"GET"}
    assert result.output["called"] == 3 and result.output["skipped"] == 0


@pytest.mark.asyncio
async def test_an_operation_missing_a_value_is_skipped_with_the_reason(monkeypatch) -> None:
    serve(monkeypatch, _shop_server)
    result = await run(ApiSweepStep, USES, {"api": API, "tags": ["materials"]}, context(shop()))
    rows = {row["operation"]: row for row in result.output["results"]}
    assert rows["getMaterial"]["verdict"] == "skipped"
    assert rows["getMaterial"]["problems"] == ["required path parameter 'id' is not in params"]
    assert "health" not in rows


@pytest.mark.asyncio
async def test_a_write_needs_include_writes_and_its_own_entry(monkeypatch) -> None:
    seen = serve(monkeypatch, _shop_server)
    methods = ["GET", "DELETE", "POST"]
    held = await run(
        ApiSweepStep,
        USES,
        {"api": API, "methods": methods, "params": {"id": "m", "limit": 1}},
        context(shop()),
    )
    assert _rows(held)["deleteMaterial"] == ("skipped", None)
    assert not [r for r in seen if r.method != "GET"]
    called = await run(
        ApiSweepStep,
        USES,
        {
            "api": API,
            "methods": methods,
            "operations": ["deleteMaterial", "createMaterial"],
            "include_writes": True,
            "params": {"id": "m"},
            "bodies": {"createMaterial": {"id": "n", "share": 1}},
        },
        context(shop()),
    )
    assert _rows(called) == {"deleteMaterial": ("passed", 204), "createMaterial": ("passed", 201)}


@pytest.mark.asyncio
async def test_an_undocumented_answer_fails_its_row_and_the_step(monkeypatch) -> None:
    serve(monkeypatch, lambda _r: httpx.Response(500, text="boom"))
    result = await run(ApiSweepStep, USES, {"api": API, "operations": ["health"]}, context(shop()))
    assert result.status == StepStatus.FAILED
    assert _rows(result) == {"health": ("failed", 500)}
    assert [c.assertion.name for c in result.assertions if not c.passed] == ["health"]


@pytest.mark.asyncio
async def test_at_most_concurrency_calls_are_in_flight(monkeypatch) -> None:
    in_flight = peak = 0

    async def slow(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return _shop_server(request)

    real = httpx.AsyncClient
    from tractusx_testlab.steps import http_client

    monkeypatch.setattr(
        http_client.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(slow), **kw),
    )
    raw = {
        "api": API,
        "params": {"id": "m", "limit": 1},
        "concurrency": 2,
        "methods": ["GET", "HEAD"],
    }
    await run(ApiSweepStep, USES, raw, context(shop()))
    assert peak == 2


@pytest.mark.asyncio
async def test_concurrency_is_bounded(monkeypatch) -> None:
    result = await run(ApiSweepStep, USES, {"api": API, "concurrency": 17}, context(shop()))
    assert "concurrency" in result.error


@pytest.mark.asyncio
async def test_calls_not_started_within_the_budget_are_skipped(monkeypatch) -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.2)
        return _shop_server(request)

    real = httpx.AsyncClient
    from tractusx_testlab.steps import http_client

    monkeypatch.setattr(
        http_client.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(slow), **kw),
    )
    raw = {"api": API, "params": {"id": "m", "limit": 1}, "concurrency": 1, "budget_s": 0.1}
    result = await run(ApiSweepStep, USES, raw, context(shop()))
    verdicts = [row["verdict"] for row in result.output["results"]]
    assert "skipped" in verdicts
    assert any("budget" in p for row in result.output["results"] for p in row["problems"])


@pytest.mark.asyncio
async def test_an_unknown_operation_is_refused_before_any_call(monkeypatch) -> None:
    seen = serve(monkeypatch, _shop_server)
    result = await run(ApiSweepStep, USES, {"api": API, "operations": ["nope"]}, context(shop()))
    assert "has no operation 'nope'" in result.error and seen == []


@pytest.mark.asyncio
async def test_every_call_stays_on_the_base_urls_host(monkeypatch) -> None:
    seen = serve(monkeypatch, _shop_server)
    await run(
        ApiSweepStep,
        USES,
        {"api": API, "base_url": "http://sut.test", "params": {"id": "m", "limit": 1}},
        context(shop()),
    )
    assert {r.url.host for r in seen} == {"sut.test"}

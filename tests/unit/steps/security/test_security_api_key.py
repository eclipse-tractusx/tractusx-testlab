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

"""security/api_key — the key placed as the security scheme says, and hidden everywhere."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from conftest import http_response
from tractusx_testlab.config.settings import TestlabConfig as _Config
from tractusx_testlab.logging import wire
from tractusx_testlab.logging.masking import forget_secrets, mask
from tractusx_testlab.logging.wire.redaction import forget_secret_headers
from tractusx_testlab.models import Job, StepDefinition, StepStatus
from tractusx_testlab.player.execution._step_outputs import hide_secrets, store_step_outputs
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.http.request import HttpRequestStep
from tractusx_testlab.steps.security.api_key import ApiKeyStep
from tractusx_testlab.steps.step_contract import StepOutput

_KEY = "ich-api-key-0123456789"
_URL = "https://ich.example/v1/part-management/catalog-part"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    forget_secret_headers()
    yield
    forget_secrets()
    forget_secret_headers()


def _context() -> StepContext:
    return StepContext(services=ServiceManager(), job=Job(job_id="api-key-run"), config=_Config())


def _step(with_: dict[str, Any], **extra: Any) -> StepDefinition:
    return StepDefinition.model_validate(
        {"id": "auth", "uses": "security/api_key", "with": with_, **extra}
    )


def _record(result: Any) -> str:
    """The step result as a trace, a report or an event writes it."""
    return json.dumps(wire.written(wire.as_recorded(result).model_dump(mode="json")))


async def _run(with_: dict[str, Any], context: StepContext | None = None, **extra: Any) -> Any:
    return await run_step(ApiKeyStep, _step(with_, **extra), "auth", context or _context())


class TestPlacement:
    @pytest.mark.asyncio
    async def test_a_header_by_default(self) -> None:
        result = await _run({"key": _KEY})
        assert result.status == StepStatus.PASSED
        assert result.output == {
            "api_key": _KEY,
            "headers": {"X-Api-Key": _KEY},
            "query": {},
            "cookies": {},
        }

    @pytest.mark.asyncio
    async def test_a_query_parameter(self) -> None:
        result = await _run({"key": _KEY, "name": "api_key", "in": "query"})
        assert (result.output["headers"], result.output["query"]) == ({}, {"api_key": _KEY})

    @pytest.mark.asyncio
    async def test_a_cookie_is_also_its_cookie_header(self) -> None:
        result = await _run({"key": _KEY, "name": "session", "in": "cookie"})
        assert result.output["cookies"] == {"session": _KEY}
        assert result.output["headers"] == {"Cookie": f"session={_KEY}"}
        assert result.output["query"] == {}


class TestRefusals:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("with_", "problem"),
        [
            ({"key": "abc"}, "at least 4 characters"),
            ({"key": f"{_KEY}\r\nX-Injected: 1"}, "line break or another control character"),
            ({"key": _KEY, "name": "X Api Key"}, "not a valid header name"),
            ({"key": f"{_KEY};path=/", "in": "cookie"}, "cannot be a cookie value"),
            ({"key": _KEY, "in": "body"}, "expected 'header', 'query' or 'cookie'"),
            ({"key": _KEY, "location": "query"}, "'location' is not a key"),
        ],
    )
    async def test_what_a_request_could_not_carry(
        self, with_: dict[str, Any], problem: str
    ) -> None:
        result = await _run(with_)
        assert result.status == StepStatus.FAILED
        assert problem in (result.error or "")

    @pytest.mark.asyncio
    async def test_a_refused_key_is_not_in_the_record(self) -> None:
        result = await _run({"key": f"{_KEY}\nmore", "name": "X Api Key"})
        assert result.status == StepStatus.FAILED
        assert _KEY not in _record(result)


class TestMasking:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("where", ["header", "query", "cookie"])
    async def test_the_key_is_in_no_record_of_the_step(self, where: str) -> None:
        result = await _run({"key": _KEY, "in": where})
        recorded = _record(result)
        assert _KEY not in recorded
        assert result.output["api_key"] == _KEY  # the run keeps it; only records mask it

    def test_the_key_is_masked_before_the_step_start_event(self) -> None:
        """``step.start`` publishes the resolved inputs before the step runs."""
        wire.mask_secret_inputs(ApiKeyStep, {"key": _KEY, "name": "X-Api-Key"}, "api-key-run")
        assert wire.written({"key": _KEY, "name": "X-Api-Key"}) == {
            "key": "***",
            "name": "X-Api-Key",
        }
        assert mask(f"key={_KEY}") == "key=***"

    @pytest.mark.asyncio
    async def test_no_returns_can_reveal_it(self) -> None:
        step = _step({"key": _KEY}, returns={"api_key": {"type": "string", "hidden": False}})
        result = await run_step(ApiKeyStep, step, "auth", _context())
        disclosure = hide_secrets(
            ApiKeyStep, step, StepOutput(value=result.output), run="api-key-run"
        )
        assert "api_key" not in disclosure.shown
        assert _KEY not in _record(result)


class TestWithHttpRequest:
    """``headers`` and ``query`` go into ``http/http_request`` unchanged."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("where", "param", "sent_as"),
        [("header", "headers", "headers"), ("query", "query_params", "params")],
    )
    async def test_the_maps_plug_in_without_glue(
        self, where: str, param: str, sent_as: str
    ) -> None:
        context = _context()
        auth = _step(
            {"key": _KEY, "in": where},
            returns={"headers": {"type": "object"}, "query": {"type": "object"}},
        )
        result = await run_step(ApiKeyStep, auth, "auth", context)
        store_step_outputs(auth, result, context, step_namespace="execution")
        output = "headers" if where == "header" else "query"
        call = StepDefinition.model_validate(
            {
                "id": "parts",
                "uses": "http/http_request",
                "with": {"url": _URL, param: f"${{{{ execution.auth.{output} }}}}"},
            }
        )
        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=http_response({"items": []}, url=_URL),
        ) as request:
            sent = await run_step(HttpRequestStep, call, "parts", context)

        assert sent.status == StepStatus.PASSED
        assert request.call_args.kwargs[sent_as] == {"X-Api-Key": _KEY}
        assert _KEY not in _record(sent)

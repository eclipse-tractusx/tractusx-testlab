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

"""security/basic — RFC 7617's Authorization header, hidden everywhere."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from conftest import http_response
from tractusx_testlab.config.settings import TestlabConfig as _Config
from tractusx_testlab.logging import wire
from tractusx_testlab.logging.masking import forget_secrets
from tractusx_testlab.logging.wire.redaction import forget_secret_headers
from tractusx_testlab.models import Job, StepDefinition, StepStatus
from tractusx_testlab.player.execution._step_outputs import store_step_outputs
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.http.request import HttpRequestStep
from tractusx_testlab.steps.security.basic import BasicAuthStep

_PASSWORD = "s3cret-pass-word"
_URL = "https://sut.example/v1/parts"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    forget_secret_headers()
    yield
    forget_secrets()
    forget_secret_headers()


def _context() -> StepContext:
    return StepContext(services=ServiceManager(), job=Job(job_id="basic-run"), config=_Config())


def _step(with_: dict[str, Any], **extra: Any) -> StepDefinition:
    return StepDefinition.model_validate(
        {"id": "auth", "uses": "security/basic", "with": with_, **extra}
    )


def _record(result: Any) -> str:
    """The step result as a trace, a report or an event writes it."""
    return json.dumps(wire.written(wire.as_recorded(result).model_dump(mode="json")))


async def _run(with_: dict[str, Any], context: StepContext | None = None) -> Any:
    return await run_step(BasicAuthStep, _step(with_), "auth", context or _context())


class TestHeader:
    @pytest.mark.asyncio
    async def test_the_rfc_7617_example(self) -> None:
        result = await _run({"username": "Aladdin", "password": "open sesame"})
        assert result.status == StepStatus.PASSED
        assert result.output == {
            "authorization": "Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==",
            "headers": {"Authorization": "Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=="},
        }

    @pytest.mark.asyncio
    async def test_credentials_are_utf8_encoded(self) -> None:
        """RFC 7617 §2.1: the charset is UTF-8 when the server asks; it is the only sane one."""
        result = await _run({"username": "test", "password": "123£"})
        token = result.output["authorization"].removeprefix("Basic ")
        assert base64.b64decode(token).decode("utf-8") == "test:123£"

    @pytest.mark.asyncio
    async def test_a_password_may_contain_a_colon(self) -> None:
        result = await _run({"username": "u", "password": "a:b"})
        token = result.output["authorization"].removeprefix("Basic ")
        assert base64.b64decode(token) == b"u:a:b"


class TestRefusals:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("with_", "problem"),
        [
            ({"username": "a:b", "password": _PASSWORD}, "username may not contain ':'"),
            ({"username": "", "password": _PASSWORD}, "at least 1 character"),
            ({"username": "u", "password": f"{_PASSWORD}\n"}, "control character"),
            ({"username": "u"}, "required key 'password' is missing"),
        ],
    )
    async def test_what_rfc_7617_does_not_allow(self, with_: dict[str, Any], problem: str) -> None:
        result = await _run(with_)
        assert result.status == StepStatus.FAILED
        assert problem in (result.error or "")

    @pytest.mark.asyncio
    async def test_a_refused_password_is_not_in_the_record(self) -> None:
        result = await _run({"username": "a:b", "password": _PASSWORD})
        assert result.status == StepStatus.FAILED
        assert _PASSWORD not in _record(result)


class TestMasking:
    @pytest.mark.asyncio
    async def test_neither_password_nor_header_is_in_the_record(self) -> None:
        result = await _run({"username": "user", "password": _PASSWORD})
        token = result.output["authorization"].removeprefix("Basic ")
        record = _record(result)
        assert _PASSWORD not in record
        assert token not in record

    @pytest.mark.asyncio
    async def test_the_header_plugs_into_http_request_and_stays_hidden(self) -> None:
        context = _context()
        auth = _step(
            {"username": "user", "password": _PASSWORD}, returns={"headers": {"type": "object"}}
        )
        result = await run_step(BasicAuthStep, auth, "auth", context)
        store_step_outputs(auth, result, context, step_namespace="execution")
        call = StepDefinition.model_validate(
            {
                "id": "parts",
                "uses": "http/http_request",
                "with": {"url": _URL, "headers": "${{ execution.auth.headers }}"},
            }
        )
        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=http_response({"items": []}, url=_URL),
        ) as request:
            sent = await run_step(HttpRequestStep, call, "parts", context)

        assert sent.status == StepStatus.PASSED
        assert request.call_args.kwargs["headers"] == {
            "Authorization": result.output["authorization"]
        }
        assert result.output["authorization"].removeprefix("Basic ") not in _record(sent)

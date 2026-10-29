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

"""Running the labs API steps the way the runner does, against a scripted server."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging import wire
from tractusx_testlab.models import Job, StepDefinition
from tractusx_testlab.openapi import BoundApiDocument
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps import http_client

Answer = Callable[[httpx.Request], httpx.Response]

#: The client class itself, taken before any test replaces it.
_CLIENT = httpx.AsyncClient


def context(*documents: BoundApiDocument) -> StepContext:
    """A run context with *documents* bound as ``${{ env.apis.<id> }}`` resolves them."""
    made = StepContext(
        services=ServiceManager(), job=Job(job_id="api-steps-run"), config=TestlabConfig()
    )
    for document in documents:
        made.set_variable(f"apis.{document.api_id}", document)
    return made


def serve(monkeypatch: pytest.MonkeyPatch, answer: Answer) -> list[httpx.Request]:
    """Answer every HTTP call a step makes with *answer*; the requests made are returned."""
    seen: list[httpx.Request] = []

    def recorded(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer(request)

    monkeypatch.setattr(
        http_client.httpx,
        "AsyncClient",
        lambda **kwargs: _CLIENT(transport=httpx.MockTransport(recorded), **kwargs),
    )
    return seen


def json_answer(status: int, body: Any, **headers: str) -> Answer:
    return lambda _request: httpx.Response(status, json=body, headers=headers)


def definition(uses: str, with_: dict[str, Any], **extra: Any) -> StepDefinition:
    return StepDefinition.model_validate({"id": "call", "uses": uses, "with": with_, **extra})


async def run(
    step_cls: type, uses: str, with_: dict[str, Any], ctx: StepContext, **extra: Any
) -> Any:
    return await run_step(step_cls, definition(uses, with_, **extra), "call", ctx)


def record(result: Any) -> str:
    """The step result as a trace, a report or an event writes it."""
    return json.dumps(wire.written(wire.as_recorded(result).model_dump(mode="json")))

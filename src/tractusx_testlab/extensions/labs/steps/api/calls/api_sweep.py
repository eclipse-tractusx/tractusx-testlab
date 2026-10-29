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

"""``labs/http/api_sweep`` — call many operations of an API file and check each. **Experimental.**"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx
from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.extensions.labs.steps.api.calls.call_contract import (
    MAX_RESPONSE_BYTES,
    ApiDocumentParams,
    answered,
)
from tractusx_testlab.extensions.labs.steps.api.calls.sweep_plan import (
    PlannedCall,
    planned,
    selected,
)
from tractusx_testlab.extensions.labs.steps.api.verdicts.verdict_report import nested, summary
from tractusx_testlab.models import StepDefinition, TestLabError
from tractusx_testlab.openapi.conformance import Problem, check_response
from tractusx_testlab.openapi.operations import (
    ApiRequestError,
    default_server_url,
    operation_index,
    prepare,
)
from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.shared_models import HttpTransportParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

USES = "labs/http/api_sweep"
MAX_CONCURRENCY = 16


class ApiSweepParams(ApiDocumentParams, HttpTransportParams):
    """Input contract of ``labs/http/api_sweep``."""

    base_url: str | None = Field(
        default=None,
        description="URL every operation's path is appended to; omitted, the document's first server URL.",
    )
    operations: list[str] = Field(
        default_factory=list,
        description="Only these operations (operationId or 'METHOD /path'); a write must be listed here.",
    )
    tags: list[str] = Field(
        default_factory=list, description="Only operations with one of these tags."
    )
    methods: list[str] = Field(
        default_factory=lambda: ["GET", "HEAD"],
        description="Only operations with one of these methods.",
    )
    exclude: list[str] = Field(default_factory=list, description="Operations never called.")
    include_writes: bool = Field(
        default=False,
        description="Call the writes listed in 'operations' (POST, PUT, PATCH, DELETE); off by default.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Path and query parameter values by name, shared by every operation; an operation missing a required one is skipped.",
    )
    query: dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters sent with every call, e.g. the 'query' 'security/api_key' returns.",
    )
    bodies: dict[str, Any] = Field(
        default_factory=dict,
        description="Request bodies by operationId (or 'METHOD /path'), for listed writes.",
    )
    concurrency: int = Field(
        default=4, ge=1, le=MAX_CONCURRENCY, description="Calls in flight at once."
    )
    budget_s: float = Field(
        default=300,
        gt=0,
        description="Seconds the whole sweep may take; calls not started by then are skipped.",
    )


class SweepRow(StepPayload):
    """One operation of the sweep and what became of it."""

    operation: str = Field(description="operationId, else 'METHOD /path'.")
    method: str = Field(description="HTTP method.")
    path: str = Field(description="Path template.")
    status: int | None = Field(default=None, description="Status answered; none when not called.")
    verdict: str = Field(description="'passed', 'failed', 'skipped' or 'error'.")
    problems: list[str] = Field(
        default_factory=list, description="What was wrong, or why it was skipped."
    )
    duration_ms: float = Field(default=0, description="Time the call took, in milliseconds.")


class ApiSweepOutput(StepPayload):
    """Output contract of ``labs/http/api_sweep``."""

    results: list[SweepRow] = Field(description="One row per operation, in document order.")
    called: int = Field(description="Operations called.")
    passed: int = Field(description="Calls whose answer the operation documents.")
    failed: int = Field(description="Calls whose answer it does not, or that failed.")
    skipped: int = Field(description="Operations not called, with the reason in their row.")


@step("labs/http/api_sweep")
class ApiSweepStep(BaseStep[ApiSweepParams, ApiSweepOutput]):
    """Call many operations of an API file and check every answer against the document.

    Safe by default: only GET and HEAD, and a write only when it is listed in
    ``operations`` *and* ``include_writes`` is true. Each operation's required
    parameters come from ``params`` (path and query, by name) and ``headers``;
    one with a value missing is skipped and its row says which. Every call goes
    to ``base_url`` — the document's per-operation ``servers`` are never
    followed, nor are redirects — at most ``concurrency`` at a time, each
    within ``timeout`` and all within ``budget_s``. Each answer is checked as
    ``labs/validate/api_response`` checks one; the step fails when any is not
    what its operation documents, and keeps the table either way.
    """

    params_model = ApiSweepParams
    output_model = ApiSweepOutput

    async def execute(
        self, params: ApiSweepParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ApiSweepOutput]:
        document = params.api
        index = operation_index(document)
        unknown = [
            name for name in [*params.operations, *params.exclude] if index.find(name) is None
        ]
        base_url = params.base_url or default_server_url(document)
        if unknown or not base_url:
            problems = [f"API '{document.api_id}' has no operation '{name}'" for name in unknown]
            problems += (
                []
                if base_url
                else ["no base_url was given and the document's first server is not absolute"]
            )
            raise ApiRequestError(USES, problems)
        chosen, held = selected(
            index,
            operations=params.operations,
            tags=params.tags,
            methods=params.methods,
            exclude=params.exclude,
            include_writes=params.include_writes,
        )
        rows: dict[str, SweepRow] = {
            op.location: _skipped(PlannedCall(op, {}, {}), why) for op, why in held
        }
        calls = [planned(op, params.params, params.headers, params.bodies) for op in chosen]
        deadline = time.monotonic() + params.budget_s
        gate = asyncio.Semaphore(params.concurrency)
        timeout = params.timeout_or(context.config.default_timeout_s)

        async def run(call: PlannedCall) -> None:
            if call.skipped:
                rows[call.operation.location] = _skipped(call, call.skipped)
                return
            async with gate:
                rows[call.operation.location] = await _call(
                    call, params, base_url, deadline, timeout, context, definition
                )

        async with asyncio.TaskGroup() as group:
            for call in calls:
                group.create_task(run(call))
        ordered = [rows[op.location] for op in index.operations if op.location in rows]
        output = ApiSweepOutput(
            results=ordered,
            called=sum(row.status is not None for row in ordered),
            passed=sum(row.verdict == "passed" for row in ordered),
            failed=sum(row.verdict in ("failed", "error") for row in ordered),
            skipped=sum(row.verdict == "skipped" for row in ordered),
        )
        checks = [
            (f"{row.operation}", [Problem("sweep", text) for text in row.problems])
            for row in ordered
            if row.verdict in ("passed", "failed", "error")
        ]
        return StepOutput(
            value=output,
            nested=nested(USES, checks),
        )


def _skipped(call: PlannedCall, reason: str) -> SweepRow:
    operation = call.operation
    return SweepRow(
        operation=operation.label,
        method=operation.method,
        path=operation.path,
        status=None,
        verdict="skipped",
        problems=[reason],
        duration_ms=0,
    )


async def _call(
    call: PlannedCall,
    params: ApiSweepParams,
    base_url: str,
    deadline: float,
    timeout: float,
    context: StepContext,
    definition: StepDefinition,
) -> SweepRow:
    operation = call.operation
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return _skipped(call, f"the sweep's budget of {params.budget_s:g} s was spent")
    started = time.monotonic()
    try:
        prepared = prepare(
            operation,
            base_url=base_url,
            path_params=call.path_params,
            query={**params.query, **call.query},
            headers=params.headers,
            body=call.body,
        )
        if urlsplit(prepared.url).netloc != urlsplit(base_url).netloc:  # defence in depth
            raise ApiRequestError(operation.label, ["the request would leave base_url's host"])
        response = await http_client.request(
            prepared.method,
            prepared.url,
            headers=prepared.headers,
            timeout=min(timeout, remaining),
            follow_redirects=False,
            max_response_bytes=MAX_RESPONSE_BYTES,
            **prepared.payload,
        )
    except (TestLabError, httpx.HTTPError) as exc:
        return _row(call, None, "error", [str(exc) or type(exc).__name__], started)
    output = answered(context, definition, params.api, operation, response, None)
    verdict = check_response(
        params.api,
        operation,
        status=output.status_code,
        headers=output.response_headers,
        body=response.text if response.content else None,
    )
    texts = [summary([problem]) for problem in verdict.problems]
    return _row(call, output.status_code, "passed" if verdict.passed else "failed", texts, started)


def _row(
    call: PlannedCall, status: int | None, verdict: str, problems: list[str], started: float
) -> SweepRow:
    operation = call.operation
    return SweepRow(
        operation=operation.label,
        method=operation.method,
        path=operation.path,
        status=status,
        verdict=verdict,
        problems=problems,
        duration_ms=round((time.monotonic() - started) * 1000, 1),
    )

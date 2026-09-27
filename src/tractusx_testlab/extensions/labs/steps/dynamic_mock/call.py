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

"""Answering one call of a ``labs/mock/api/dynamic`` mock. **Experimental.**

The mock server hands the call to :class:`CallHandler` on its own event loop.
The mock's steps run on the loop of the run that registered it instead —
that is where the run's services live — and the server waits for the reply
without blocking the loop it serves other calls on.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.primitives.exceptions import TestLabError
from tractusx_testlab.server.mock_registry import MockRequest, MockResponse
from tractusx_testlab.syntax import call_scope

if TYPE_CHECKING:
    from tractusx_testlab.extensions.labs.steps.dynamic_mock.params import DynamicMockParams
    from tractusx_testlab.models import StepDefinition
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

#: What the caller is told when no reply could be worked out. Why is logged,
#: not sent: the reason names the test's variables, and the caller is the
#: system under test.
_NO_REPLY = {"detail": "The mock could not work out its reply to this call."}


class CallHandler:
    """The mock's handler: runs ``process`` for a call, then reads the reply."""

    def __init__(
        self,
        params: DynamicMockParams,
        context: StepContext,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._params = params
        self._context = context
        self._loop = loop

    async def __call__(self, request: MockRequest) -> MockResponse:
        answer = self._answer(request)
        try:
            future = asyncio.run_coroutine_threadsafe(answer, self._loop)
        except RuntimeError:
            answer.close()
            return _no_reply(request, "the run that registered the mock has ended")
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), self._params.process_timeout)
        except TimeoutError:
            future.cancel()
            return _no_reply(
                request, f"its steps took longer than {self._params.process_timeout:g}s"
            )

    async def _answer(self, request: MockRequest) -> MockResponse:
        call = _call_context(self._context, request)
        failure = await _run_process(self._params.process, call)
        if failure:
            return _no_reply(request, failure)
        try:
            return _read_reply(self._params, call)
        except (TestLabError, TypeError, ValueError) as exc:
            return _no_reply(request, f"its reply could not be read: {exc}")


def _call_context(run: StepContext, request: MockRequest) -> StepContext:
    """A context for one call: the run's variables, the call, and a namespace of its own.

    A copy, so that two calls answered at once, or a call answered while the
    run goes on, never see each other's values — and so nothing a call's
    steps publish reaches the run. No reporters are bound: the run's live view
    shows its phases in order, and a call can arrive in the middle of any step.
    """
    call = type(run)(run.services, run.job, run.config, run.infrastructure)
    for name, value in run.variables.items():
        if run.is_template(name):
            call.set_template(name, value)
        else:
            call.set_variable(name, value)
    call.bind_invoker(run.invoke_step)
    call.bind_test_cac(run.test_cac)
    call.bind_step_namespace(call_scope.PROCESS)
    for field, value in _request_fields(request).items():
        call.set_variable(call_scope.request_variable(field), value)
    return call


def _request_fields(request: MockRequest) -> dict[str, Any]:
    """The call as ``*.request.<field>`` — see ``call_scope.REQUEST_FIELDS``."""
    return {
        "body": request.body,
        "headers": {str(name).lower(): value for name, value in request.headers.items()},
        # One value per name, as ``mock/wait`` publishes it: the last one given.
        "query": {name: values[-1] for name, values in request.query_params.items() if values},
        "method": request.method,
        "path": request.path,
    }


async def _run_process(steps: list[StepDefinition], call: StepContext) -> str:
    """Run the mock's steps in order; why the first one that failed did, or ``""``."""
    for index, nested in enumerate(steps):
        step_name = f"process[{index}]:{nested.uses}"
        step_cls = StepRegistry.get_any(nested.uses)
        if step_cls is None:
            return f"no step '{nested.uses}' is registered"
        result = await call.invoke_step(step_cls, nested, step_name, call)
        if result.status == StepStatus.FAILED:
            return f"step {step_name} failed: {result.error or 'assertion failed'}"
    return ""


def _read_reply(params: DynamicMockParams, call: StepContext) -> MockResponse:
    """The reply, every ``${{ }}`` in it read against the call's context."""
    # Imported here: the player imports the steps to register them.
    from tractusx_testlab.player.loading.resolver import resolve_params

    reply = resolve_params(
        {
            "status": params.response_status,
            "body": params.response_body,
            "headers": params.response_headers,
        },
        call,
    )
    headers = reply["headers"]
    if not isinstance(headers, dict):
        raise TypeError(f"response_headers must be a mapping, got {type(headers).__name__}")
    return MockResponse(
        status_code=int(reply["status"]),
        body=reply["body"],
        headers={str(name): str(value) for name, value in headers.items()},
    )


def _no_reply(request: MockRequest, reason: str) -> MockResponse:
    logger.warning(
        "Dynamic mock %s %s answered 500: %s",
        request.method,
        request.path[:80].replace("\n", "").replace("\r", ""),
        reason,
    )
    return MockResponse(status_code=500, body=dict(_NO_REPLY))

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Wait steps — block until a mock endpoint receives an inbound request.

``mock/wait/http_request`` waits for a call the system under test makes to the
mock URL itself. ``mock/wait/dataplane/http_request`` waits for one that must
arrive through the engine connector's data plane, for a named asset whose data
address is the mock.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, cast

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import (
    ConnectorOffer,
    ExecutionError,
    Listener,
    StepDefinition,
    WaitBrief,
)
from tractusx_testlab.server.inbound.run_scope import declared, scoped
from tractusx_testlab.server.mock_registry import get_callback_manager
from tractusx_testlab.steps.mock._models import MockInstance
from tractusx_testlab.steps.mock._paused_wait import wait_through_pauses
from tractusx_testlab.steps.shared_models import StepParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 30.0


class WaitForCallParams(StepParams):
    """Input contract of ``mock/wait/http_request``.

    The mock arrives as the object the step that registered it returned, not as
    a URL or an ID to look up again: the mock already knows its own path and
    method, so there is nothing left for this step to guess.
    """

    mock: MockInstance = Field(
        description="The mock to wait on, as returned by the step that registered it."
    )
    timeout_s: float = Field(
        default=_DEFAULT_TIMEOUT_S, gt=0, description="Seconds to wait before failing."
    )
    brief: WaitBrief | None = Field(
        default=None,
        description=(
            "What the run tells the person driving the system under test while it waits: "
            "a message, the steps to take in order, and labelled values to copy. Shown in "
            "place of what a viewer would otherwise derive from the listener."
        ),
    )


class WaitForDataplaneCallParams(WaitForCallParams):
    """Input contract of ``mock/wait/dataplane/http_request``."""

    asset_id: str = Field(
        min_length=1,
        description=(
            "The asset on the engine connector whose data address is the mock — the "
            "offer the system under test negotiates to reach it."
        ),
    )
    dct_type: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "dct:type of that asset. Announced so the system under test finds the offer "
            "by what it is, with a catalog filter, rather than by the asset id, which "
            "usually carries the run's id."
        ),
    )
    dct_subject: str | None = Field(
        default=None, min_length=1, description="dct:subject of that asset, when it has one."
    )
    version: str | None = Field(
        default=None, min_length=1, description="cx-common:version of that asset, e.g. 3.0."
    )


class InboundCallOutput(StepPayload):
    """The inbound request a mock endpoint received."""

    request_method: str = Field(description="HTTP method of the inbound request.")
    request_path: str = Field(description="Path the request arrived on.")
    request_headers: dict[str, str] = Field(
        default_factory=dict, description="Headers of the inbound request."
    )
    request_query_params: dict[str, str] = Field(
        default_factory=dict, description="Query string parameters of the inbound request."
    )
    request_body: Any = Field(default=None, description="Body of the inbound request.")
    elapsed_ms: int = Field(description="Milliseconds spent waiting before the request arrived.")


@step("mock/wait/http_request")
class WaitForCallStep(BaseStep[WaitForCallParams, InboundCallOutput]):
    """Wait for an inbound HTTP request on a previously-registered mock endpoint.

    This is the other half of ``mock/api``: that step hands the system under
    test a callback URL, and this one blocks until the SUT calls it, then hands
    the request it made to the assertions.

    A call the mock turns away — no key, another run's key, the wrong method
    or path — fails the wait as soon as it arrives, saying which
    (``MockCallRefusedError``); only the call the mock answers ends it well.

    Pausing the run stops the wait where it is: the listener closes, the
    timeout stops counting (``step_suspended`` says how much is left), and the
    run goes on hold (``player.execution.hold``). On resume the listener opens
    again and the wait carries on for the time it had left, announced by a
    fresh ``step_waiting``. ``elapsed_ms`` counts only the time spent waiting.

    Raises:
        RuntimeError: If no ``CallbackManager`` is available or the wait times out.
        MockCallRefusedError: If the call the wait was for was refused.
    """

    # Widened like OAuth2GetTokenStep's, so the dataplane wait can narrow it.
    params_model: ClassVar[type[StepParams]] = WaitForCallParams
    output_model = InboundCallOutput

    def listener(self, params: WaitForCallParams, context: StepContext) -> Listener:
        """Where the call is expected, as the run announces it."""
        return Listener(
            method=params.mock.method,
            url=params.mock.full_mock_url,
            path=params.mock.path,
            brief=params.brief,
        )

    async def execute(
        self, params: WaitForCallParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[InboundCallOutput]:
        path = params.mock.path
        method = params.mock.method
        timeout = params.timeout_s
        # The listener of this run's mock, kept under the run's own address:
        # another run waiting on the same path waits on a listener of its own.
        key_path = scoped(str(context.job.job_id), path)

        manager = get_callback_manager()
        if manager is None:
            raise RuntimeError(
                "No CallbackManager available — wait_for_call requires the TestLab server"
            )

        manager.register(key_path, method)
        listener = self.listener(params, context)
        # The run is now blocked on the SUT. Said out loud, with the address,
        # because from here the only thing that moves the run forward is a
        # call to it — and if the SUT will not make it, a person has to.
        context.report_waiting(definition.uses, definition.id, listener, timeout)
        logger.info("Waiting up to %.0fs for %s %s", timeout, method, path)

        result, waited_s = await wait_through_pauses(
            manager, context, definition, listener, timeout, key_path=key_path
        )
        elapsed_ms = round(waited_s * 1000)

        if result.timed_out:
            raise RuntimeError(_timed_out(manager, timeout, method, key_path))
        if result.refused is not None:
            raise MockCallRefusedError(listener, result.refused, elapsed_ms)

        context.report_received(definition.uses, definition.id, listener, result, elapsed_ms)
        logger.info("Received callback on %s %s after %dms", method, path, elapsed_ms)
        return StepOutput(
            value=InboundCallOutput(
                request_method=result.method,
                request_path=result.path,
                request_headers=result.headers,
                request_query_params=result.query_params,
                request_body=result.payload,
                elapsed_ms=elapsed_ms,
            )
        )


@step("mock/wait/dataplane/http_request")
class WaitForDataplaneCallStep(WaitForCallStep):
    """Wait for an inbound HTTP request that arrives through the engine connector's data plane.

    The same wait as ``mock/wait/http_request``, for a mock the system under
    test must not call directly: a test offers an asset on the engine connector
    whose data address is the mock, and the SUT negotiates that asset and calls
    through its data plane. What differs is what the run announces — not the
    mock URL, which is only the data plane's target, but the offer to negotiate:
    the asset (by dct:type, dct:subject and version when given), and the engine
    connector's DSP URL and identity from the run's infrastructure binding.
    """

    params_model = WaitForDataplaneCallParams

    def listener(self, params: WaitForCallParams, context: StepContext) -> Listener:
        # Validated against this step's own params_model, so the asset is there.
        offer = cast(WaitForDataplaneCallParams, params)
        connector = context.infrastructure.engine.connector
        return Listener(
            method=params.mock.method,
            url=params.mock.full_mock_url,
            path=params.mock.path,
            via="dataplane",
            offer=ConnectorOffer(
                asset_id=offer.asset_id,
                dsp_url=_text(connector.dsp_url),
                participant_id=_text(connector.participant_id),
                dct_type=offer.dct_type,
                dct_subject=offer.dct_subject,
                version=offer.version,
            ),
            brief=offer.brief,
        )


class MockCallRefusedError(ExecutionError):
    """The call the wait was for arrived in a form the mock does not accept.

    A result about the system under test, and one reached as soon as the call
    came: it had no key (it did not come through the connector that carries
    it), another run's key, or went to another address than the one waited on.
    Waiting on after it would only turn a precise finding into a timeout.
    """

    code = "MOCK_CALL_REFUSED"

    def __init__(self, listener: Listener, reason: str, elapsed_ms: int) -> None:
        through = (
            "; the call has to reach the mock through the engine connector's data plane"
            f", for asset {listener.offer.asset_id}"
            if listener.via == "dataplane" and listener.offer is not None
            else ""
        )
        super().__init__(
            f"Refused a call while waiting for {listener.method} {listener.path}: {reason}{through}"
        )
        self.diagnostics = {
            "reason": reason,
            "expected": {"method": listener.method, "path": listener.path},
            "waited_ms": elapsed_ms,
        }


def _timed_out(manager: Any, timeout: float, method: str, path: str) -> str:
    """Why the wait failed — including calls that arrived and were turned away.

    A mock that requires a key refuses a call without it (``mock/api``'s
    ``require_api_key``). Such a call did reach the mock, just not through the
    connector, and a bare "timed out" would send whoever reads it looking for a
    network problem instead.
    """
    message = f"Timed out after {timeout}s waiting for {method} {declared(path)}"
    refused = manager.refused(path, method) if hasattr(manager, "refused") else 0
    if isinstance(refused, int) and refused > 0:
        message += (
            f"; {refused} call(s) reached the mock without the key the connector "
            "adds and were refused — the call has to go through the engine "
            "connector's data plane, not to the mock URL directly"
        )
    return message


def _text(value: object) -> str | None:
    """A binding field as published — ``None`` for one the run left empty."""
    return value if isinstance(value, str) and value else None

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
## It was reviewed and tested by a human committer.

"""Wait steps — block until a mock endpoint receives an inbound request.

``mock/wait/http_request`` waits for a call the system under test makes to the
mock URL itself. ``mock/wait/dataplane/http_request`` waits for one that must
arrive through the engine connector's data plane, for a named asset whose data
address is the mock.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from pydantic import Field

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import ConnectorOffer, Listener, StepDefinition
from tractusx_testlab.server.mock_registry import get_callback_manager
from tractusx_testlab.steps.mock._models import MockInstance
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


class WaitForDataplaneCallParams(WaitForCallParams):
    """Input contract of ``mock/wait/dataplane/http_request``."""

    asset_id: str = Field(
        min_length=1,
        description=(
            "The asset on the engine connector whose data address is the mock — the "
            "offer the system under test negotiates to reach it."
        ),
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

    Raises:
        RuntimeError: If no ``CallbackManager`` is available or the wait times out.
    """

    params_model: type[WaitForCallParams] = WaitForCallParams
    output_model = InboundCallOutput

    def listener(self, params: WaitForCallParams, context: StepContext) -> Listener:
        """Where the call is expected, as the run announces it."""
        return Listener(
            method=params.mock.method, url=params.mock.full_mock_url, path=params.mock.path
        )

    async def execute(
        self, params: WaitForCallParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[InboundCallOutput]:
        path = params.mock.path
        method = params.mock.method
        timeout = params.timeout_s

        manager = get_callback_manager()
        if manager is None:
            raise RuntimeError(
                "No CallbackManager available — wait_for_call requires the TestLab server"
            )

        manager.register(path, method)
        listener = self.listener(params, context)
        # The run is now blocked on the SUT. Said out loud, with the address,
        # because from here the only thing that moves the run forward is a
        # call to it — and if the SUT will not make it, a person has to.
        context.report_waiting(definition.uses, definition.id, listener, timeout)
        logger.info("Waiting up to %.0fs for %s %s", timeout, method, path)

        started = time.monotonic()
        result = await manager.wait(path, method, timeout)
        elapsed_ms = round((time.monotonic() - started) * 1000)

        if result.timed_out:
            raise RuntimeError(f"Timed out after {timeout}s waiting for {method} {path}")

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
    the asset, and the engine connector's DSP URL and identity from the run's
    infrastructure binding.
    """

    params_model = WaitForDataplaneCallParams

    def listener(self, params: WaitForCallParams, context: StepContext) -> Listener:
        # Validated against this step's own params_model, so the asset is there.
        asset_id = cast(WaitForDataplaneCallParams, params).asset_id
        connector = context.infrastructure.engine.connector
        return Listener(
            method=params.mock.method,
            url=params.mock.full_mock_url,
            path=params.mock.path,
            via="dataplane",
            offer=ConnectorOffer(
                asset_id=asset_id,
                dsp_url=_text(connector.dsp_url),
                participant_id=_text(connector.participant_id),
            ),
        )


def _text(value: object) -> str | None:
    """A binding field as published — ``None`` for one the run left empty."""
    return value if isinstance(value, str) and value else None

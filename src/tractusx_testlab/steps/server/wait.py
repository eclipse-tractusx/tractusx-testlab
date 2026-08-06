#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4).
## It was reviewed and tested by a human committer.

"""wait_for_call step — blocks until a mock endpoint receives an inbound request."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.server.mock_registry import get_callback_manager
from tractusx_testlab.steps._contracts import StepParams
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 30.0


def _extract_path_from_endpoint_url(endpoint_url: str) -> str:
    """Extract the callback path from a mock endpoint URL.

    The ``MockEndpointStep`` output is a full URL like
    ``http://localhost:8080/companycertificate/status``.
    We need just ``/companycertificate/status``.
    """
    return urlparse(endpoint_url).path


class WaitForCallParams(StepParams):
    """Input contract of ``mock/wait/http_request``."""

    endpoint_id: str = Field(
        description=(
            "A mock endpoint's URL, the ID it was registered under, or the path "
            "itself — all three are accepted."
        ),
    )
    method: str = Field(default="POST", description="HTTP method to wait for.")
    timeout_s: float = Field(
        default=_DEFAULT_TIMEOUT_S, gt=0, description="Seconds to wait before failing."
    )

    @field_validator("method")
    @classmethod
    def _uppercase_method(cls, value: str) -> str:
        """Accept ``post`` as readily as ``POST``."""
        return value.upper()


class InboundCallOutput(StepPayload):
    """The inbound request a mock endpoint received."""

    method: str = Field(description="HTTP method of the inbound request.")
    path: str = Field(description="Path the request arrived on.")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Headers of the inbound request."
    )
    body: Any = Field(default=None, description="Body of the inbound request.")


@step("mock/wait/http_request")
class WaitForCallStep(BaseStep[WaitForCallParams, InboundCallOutput]):
    """Wait for an inbound HTTP request on a previously-registered mock endpoint.

    This is the other half of ``mock/api``: that step hands the system under
    test a callback URL, and this one blocks until the SUT calls it, then hands
    the request it made to the assertions.

    Raises:
        RuntimeError: If no ``CallbackManager`` is available or the wait times out.
    """

    params_model = WaitForCallParams
    output_model = InboundCallOutput

    async def execute(
        self, params: WaitForCallParams, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput[InboundCallOutput]:
        raw_endpoint_id = params.endpoint_id
        method = params.method
        timeout = params.timeout_s

        manager = get_callback_manager()
        if manager is None:
            raise RuntimeError(
                "No CallbackManager available — wait_for_call requires the TestLab server"
            )

        # endpoint_id may be a full URL (from a previous step output) or a plain
        # string ID referencing a mock registered via MockEndpointStep.  When it
        # looks like a URL we parse the path directly; otherwise we look up the
        # context variable that MockEndpointStep stored under that ID.
        if raw_endpoint_id.startswith(("http://", "https://")):  # NOSONAR — detecting URL scheme in user input, not constructing an insecure connection
            full_path = _extract_path_from_endpoint_url(raw_endpoint_id)
        else:
            stored_url = context.get_variable(raw_endpoint_id)
            if stored_url and isinstance(stored_url, str) and stored_url.startswith(("http://", "https://")):  # NOSONAR — detecting URL scheme in stored variable, not constructing an insecure connection
                full_path = _extract_path_from_endpoint_url(stored_url)
            else:
                # Treat the raw value as a path fragment
                full_path = f"/{raw_endpoint_id}" if not raw_endpoint_id.startswith("/") else raw_endpoint_id

        manager.register(full_path, method)
        logger.info("Waiting up to %.0fs for %s %s", timeout, method, full_path)

        result = await manager.wait(full_path, method, timeout)

        if result.timed_out:
            raise RuntimeError(
                f"Timed out after {timeout}s waiting for {method} {full_path}"
            )

        logger.info("Received callback on %s %s", method, full_path)
        return StepOutput(
            value=InboundCallOutput(
                method=result.method,
                path=result.path,
                headers=result.headers,
                body=result.payload,
            )
        )

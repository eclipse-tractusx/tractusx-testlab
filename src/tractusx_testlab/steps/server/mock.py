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

"""mock_endpoint step — registers a canned HTTP response on the mock server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.server.mock_registry import (
    MockResponse,
    get_callback_manager,
    register_mock,
)
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepValue
from tractusx_testlab.steps.server._contracts import MockIdParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_VARIABLE_PREFIX = "@"


def _resolve_variables(obj: dict | list | str, context: "StepContext") -> dict | list | str:
    """Recursively replace ``@var`` references in response bodies."""
    if isinstance(obj, str):
        if obj.startswith(_VARIABLE_PREFIX):
            var_name = obj[len(_VARIABLE_PREFIX):]
            return context.get_variable(var_name, obj)
        return obj
    if isinstance(obj, dict):
        return {k: _resolve_variables(v, context) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_variables(item, context) for item in obj]
    return obj


<<<<<<< HEAD
class MockEndpointParams(MockIdParams):
    """Input contract of ``mock/api``."""

    path: str = Field(description="URL path to register, e.g. '/companycertificate/request'.")
    method: str = Field(default="POST", description="HTTP method the mock answers on.")
    response_status: int = Field(default=200, description="Status code the mock returns.")
    response_body: Any = Field(
        default_factory=dict,
        description="JSON body the mock returns; '@name' strings resolve to context variables.",
    )

    @field_validator("method")
    @classmethod
    def _uppercase_method(cls, value: str) -> str:
        """Accept ``post`` as readily as ``POST``."""
        return value.upper()

    @field_validator("path")
    @classmethod
    def _absolute_path(cls, value: str) -> str:
        """The path must match the URL the SUT will call, leading slash included."""
        return value if value.startswith("/") else f"/{value}"


class MockEndpointOutput(StepValue[str]):
    """The full callback URL of the registered endpoint."""


@step("mock/api")
class MockEndpointStep(BaseStep[MockEndpointParams, MockEndpointOutput]):
=======
@step("mock/api")
class MockEndpointStep(BaseStep):
>>>>>>> 4151bc2 (Refactor step identifiers for consistency and clarity)
    """Register a mock HTTP endpoint that returns a canned response.

    The returned URL is what a script hands to the system under test as its
    callback address; ``mock/wait/http_request`` then blocks until the SUT calls
    it.
    """

    params_model = MockEndpointParams
    output_model = MockEndpointOutput

    async def execute(
        self, params: MockEndpointParams, context: "StepContext", definition: StepDefinitionV2
    ) -> StepOutput[MockEndpointOutput]:
        resolved_body = _resolve_variables(params.response_body, context)
        register_mock(
            params.path,
            params.method,
            MockResponse(status_code=params.response_status, body=resolved_body),
        )

        # Pre-register a callback listener so wait_for_call can block on it
        callback_manager = get_callback_manager()
        if callback_manager is not None:
            callback_manager.register(params.path, params.method)

        endpoint_url = f"http://localhost:{context.config.server_port}{params.path}"
        params.publish_url(endpoint_url, context)

        logger.info(
            "Registered mock endpoint %s %s -> %d",
            params.method, params.path, params.response_status,
        )
        return StepOutput(value=MockEndpointOutput(endpoint_url))

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

"""security/api_key — present an API key where the API's security scheme says.

An OpenAPI ``apiKey`` security scheme names the key's carrier — a header, a
query parameter or a cookie — and its name. This step takes the key and the
two, and returns the maps a request step merges in as they are:

.. code-block:: yaml

    - id: auth
      uses: security/api_key
      with: { key: "${{ env.ich_api_key }}", name: X-Api-Key }
    - id: list_parts
      uses: http/http_request
      with:
        url: "${{ env.ich_url }}/v1/part-management/catalog-part"
        headers: "${{ execution.auth.headers }}"

Nothing is called. The key is hidden in every record of the run — the step's
inputs, its outputs, the request a later step sends with it, a refusal of the
key itself — and no ``returns:`` can show it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

from pydantic import Field, model_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.logging.masking import MIN_EXPLICIT_LENGTH
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.security._credential_inputs import (
    HEADER_NAME,
    is_cookie_safe,
    is_header_safe,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class ApiKeyParams(StepParams):
    """Input contract of ``security/api_key``."""

    key: str = Field(
        min_length=MIN_EXPLICIT_LENGTH,
        description=(
            f"The API key, at least {MIN_EXPLICIT_LENGTH} characters. Hidden in every "
            "record of the run."
        ),
        json_schema_extra={"secret": True},
    )
    name: str = Field(
        default="X-Api-Key",
        min_length=1,
        description="Name of the header, query parameter or cookie the API reads the key from.",
    )
    in_: Literal["header", "query", "cookie"] = Field(
        default="header",
        validation_alias="in",
        serialization_alias="in",
        description="Where the key is sent: as a header, a query parameter or a cookie.",
    )

    @model_validator(mode="after")
    def _sendable_as_declared(self) -> Self:
        """Refuse a name or key the request could not carry where ``in`` says.

        The messages never quote the key.
        """
        if self.in_ in ("header", "cookie") and not HEADER_NAME.match(self.name):
            raise ValueError(
                f"name '{self.name}' is not a valid {self.in_} name: use letters, digits "
                "and !#$%&'*+-.^_`|~, without spaces"
            )
        if self.in_ == "header" and not is_header_safe(self.key):
            raise ValueError("key contains a line break or another control character")
        if self.in_ == "cookie" and not is_cookie_safe(self.key):
            raise ValueError(
                "key cannot be a cookie value: it contains a space, a quote, a comma, "
                "a semicolon, a backslash or a control character"
            )
        return self


class ApiKeyOutput(StepPayload):
    """The key, and where to put it — each map ready to hand a request step."""

    api_key: str = Field(
        description="The API key. Hidden in every record of the run.",
        json_schema_extra={"secret": True, "class": "AuthToken"},
    )
    headers: dict[str, str] = Field(
        description=(
            "Headers to send: '{name: key}' for in: header, 'Cookie: name=key' for "
            "in: cookie, empty for in: query."
        ),
        json_schema_extra={"secret": True},
    )
    query: dict[str, str] = Field(
        description="Query parameters to send: '{name: key}' for in: query, else empty.",
        json_schema_extra={"secret": True},
    )
    cookies: dict[str, str] = Field(
        description="Cookies to send: '{name: key}' for in: cookie, else empty.",
        json_schema_extra={"secret": True},
    )


@step("security/api_key")
class ApiKeyStep(BaseStep[ApiKeyParams, ApiKeyOutput]):
    """Place an API key in a header, a query parameter or a cookie.

    For an API whose OpenAPI ``apiKey`` security scheme names where the key goes.
    ``headers`` plugs into ``http/http_request``'s ``headers`` and ``query``
    into its ``query_params`` unchanged; a cookie is sent as a ``Cookie``
    header, so ``headers`` carries it too. Nothing is called. The key is hidden
    in every record of the run, and no ``returns:`` can show it.
    """

    params_model = ApiKeyParams
    output_model = ApiKeyOutput

    async def execute(
        self, params: ApiKeyParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ApiKeyOutput]:
        placed = {params.name: params.key}
        return StepOutput(
            value=ApiKeyOutput(
                api_key=params.key,
                headers=(
                    placed
                    if params.in_ == "header"
                    else {"Cookie": f"{params.name}={params.key}"}
                    if params.in_ == "cookie"
                    else {}
                ),
                query=placed if params.in_ == "query" else {},
                cookies=placed if params.in_ == "cookie" else {},
            )
        )

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

"""security/basic — the ``Authorization`` header of HTTP Basic authentication.

For an API whose OpenAPI ``http`` security scheme says ``scheme: basic``
(RFC 7617): the user id and password, joined by a colon, UTF-8 encoded and
base64 encoded, after ``Basic``:

.. code-block:: yaml

    - id: auth
      uses: security/basic
      with: { username: "${{ env.sut_user }}", password: "${{ env.sut_password }}" }
    - id: list_parts
      uses: http/http_request
      with:
        url: "${{ env.sut_url }}/v1/parts"
        headers: "${{ execution.auth.headers }}"

Nothing is called. The password and the header are hidden in every record of
the run, and no ``returns:`` can show them.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Self

from pydantic import Field, model_validator

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.logging.masking import register_secret
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.security._credential_inputs import is_header_safe
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class BasicAuthParams(StepParams):
    """Input contract of ``security/basic``."""

    username: str = Field(min_length=1, description="User id. May not contain a colon (RFC 7617).")
    password: str = Field(
        description="Password. Hidden in every record of the run.",
        json_schema_extra={"secret": True},
    )

    @model_validator(mode="after")
    def _encodable(self) -> Self:
        """Refuse what RFC 7617 does not allow. The messages never quote the password."""
        if ":" in self.username:
            raise ValueError("username may not contain ':' — it separates user id and password")
        if not (is_header_safe(self.username) and is_header_safe(self.password)):
            raise ValueError("username or password contains a control character")
        return self

    def authorization(self) -> str:
        """The ``Authorization`` header value for these credentials."""
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode("ascii")
        return f"Basic {token}"


class BasicAuthOutput(StepPayload):
    """The ``Authorization`` value, alone and as a header map ready to hand a request step."""

    authorization: str = Field(
        description="'Basic <base64(username:password)>'. Hidden in every record of the run.",
        json_schema_extra={"secret": True, "class": "AuthToken"},
    )
    headers: dict[str, str] = Field(
        description="'{Authorization: Basic …}', for a request step's 'headers'.",
        json_schema_extra={"secret": True},
    )


@step("security/basic")
class BasicAuthStep(BaseStep[BasicAuthParams, BasicAuthOutput]):
    """Build the ``Authorization`` header of HTTP Basic authentication.

    For an API whose OpenAPI ``http`` security scheme says ``scheme: basic``
    (RFC 7617). ``headers`` plugs into ``http/http_request``'s ``headers``
    unchanged. Nothing is called. The password and the header are hidden in
    every record of the run, and no ``returns:`` can show them.
    """

    params_model = BasicAuthParams
    output_model = BasicAuthOutput

    async def execute(
        self, params: BasicAuthParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[BasicAuthOutput]:
        authorization = params.authorization()
        # The outputs are hidden whole; the token is hidden on its own too, for
        # a record that carries it without the scheme in front.
        register_secret(
            authorization.removeprefix("Basic "), run=str(context.job.job_id), explicit=True
        )
        return StepOutput(
            value=BasicAuthOutput(
                authorization=authorization, headers={"Authorization": authorization}
            )
        )

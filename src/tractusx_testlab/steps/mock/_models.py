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

"""Contract models shared by the mock-server steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, model_validator

from tractusx_testlab.models.runtime.listener import WaitAction
from tractusx_testlab.steps.shared_models import StepParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class MockInstance(BaseModel):
    """A registered mock, as the steps that use it later need to see it.

    ``mock/wait/http_request`` waits on a mock rather than on a URL it has to
    take apart again, so what ``mock/api`` returns is the mock itself: where it
    listens, for what, and at which address the system under test can reach it.
    """

    endpoint_id: str = Field(
        default="", description="Identifier the mock was registered under, when it was given one."
    )
    path: str = Field(description="Path the mock listens on.")
    method: str = Field(description="HTTP method the mock answers.")
    base_mock_url: str = Field(description="Root URL of the testlab mock server.")
    full_mock_url: str = Field(description="Address the system under test calls — root plus path.")


class MockIdParams(StepParams):
    """Names the mock a step registers.

    The ID doubles as a context variable name for steps that publish a URL, so
    what it stands for comes from the test rather than from the step — which
    is why it cannot be a declared output field.
    """

    id: str = Field(
        default="",
        description="Identifier for the registered mock; also the variable its URL is stored under.",
    )

    def publish_url(self, url: str, context: StepContext) -> None:
        """Store *url* under this mock's ID, when it was given one."""
        if self.id:
            context.set_variable(self.id, url)


class RequiredMockIdParams(MockIdParams):
    """For mocks that stand for a whole service, where the ID is not optional."""

    id: str = Field(min_length=1, description="Unique identifier for the registered mock.")


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
    action: WaitAction | None = Field(
        default=None,
        description=(
            "The action the system under test has to take while the run waits: 'label', "
            "'description', 'recommendation' (the steps, in order) and 'fields' (labelled "
            "values to copy). Shown in place of what a viewer would derive from the listener."
        ),
    )


class WaitForDataplaneCallParams(WaitForCallParams):
    """Input contract of ``mock/wait/dataplane/http_request``."""

    asset_id: str = Field(
        default="",
        description=(
            "The asset on the engine connector whose data address is the mock — the "
            "offer the system under test negotiates to reach it. Optional when 'asset' "
            "carries it."
        ),
    )
    asset: dict[str, Any] | None = Field(
        default=None,
        description=(
            "That asset as configured: a 'config/connector/asset' or "
            "'config/connector/mock_asset' value, e.g. '${{ env.ccmapi_asset }}'. Its "
            "public properties ('dct_type', 'dct_subject', 'version', 'semantic_id', "
            "'properties') are announced, so the system under test finds the offer by "
            "what it is instead of by the asset id, which usually carries the run's id. "
            "Its 'private_properties' are never announced."
        ),
    )

    @model_validator(mode="after")
    def _names_the_asset(self) -> WaitForDataplaneCallParams:
        if isinstance(self.asset, dict) and isinstance(self.asset.get("asset"), dict):
            self.asset = self.asset["asset"]
        if not self.asset_id and self.asset:
            self.asset_id = str(self.asset.get("asset_id") or "")
        if not self.asset_id:
            raise ValueError("name the asset: 'asset_id', or an 'asset' that carries one")
        return self

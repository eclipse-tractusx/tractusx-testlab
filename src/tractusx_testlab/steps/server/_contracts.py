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

"""Contract models shared by the mock-server steps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.steps._contracts import StepParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class MockIdParams(StepParams):
    """Names the mock a step registers.

    The ID doubles as a context variable name for steps that publish a URL, so
    what it stands for comes from the script rather than from the step — which
    is why it cannot be a declared
    :class:`~tractusx_testlab.steps.base.StepExports` field.
    """

    id: str = Field(
        default="",
        description="Identifier for the registered mock; also the variable its URL is stored under.",
    )

    def publish_url(self, url: str, context: "StepContext") -> None:
        """Store *url* under this mock's ID, when it was given one."""
        if self.id:
            context.set_variable(self.id, url)


class RequiredMockIdParams(MockIdParams):
    """For mocks that stand for a whole service, where the ID is not optional."""

    id: str = Field(min_length=1, description="Unique identifier for the registered mock.")

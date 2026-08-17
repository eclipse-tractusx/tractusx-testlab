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

"""Delay step — pauses test execution for a fixed duration."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps._contracts import NoOutput
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# flow/delay
# ---------------------------------------------------------------------------


class DelayParams(StepParams):
    """Input contract of ``flow/delay``."""

    seconds: float = Field(default=1, ge=0, description="Seconds to wait.")


@step("flow/delay")
class DelayStep(BaseStep[DelayParams, NoOutput]):
    """Pause test execution for a fixed duration.

    Useful where a system under test needs a moment to reach the state the
    next step asserts on and offers nothing to poll.
    """

    params_model = DelayParams
    output_model = NoOutput

    async def execute(
        self, params: DelayParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[NoOutput]:
        await asyncio.sleep(params.seconds)
        return StepOutput(value=NoOutput(None))

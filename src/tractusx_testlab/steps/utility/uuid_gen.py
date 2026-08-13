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

"""UUID generation step — produces a random UUID v4."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.base import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class GenerateUuidParams(StepParams):
    """Input contract of ``util/generate_uuid``."""

    prefix: str = Field(
        default="",
        description="Text prepended to the UUID, e.g. 'urn:uuid:'.",
    )


class GenerateUuidOutput(StepPayload):
    """Output contract of ``util/generate_uuid``.

    One key, because there is one value.  This step used to publish it twice —
    as ``uuid`` and again as ``generated_id`` — and a second spelling of the
    same value is a second thing to keep in step for no gain: two scripts read
    the same identifier under two names and neither reads the step's contract.
    """

    uuid: str = Field(description="The generated identifier, including any prefix.")


@step("util/generate_uuid")
class GenerateUuidStep(BaseStep[GenerateUuidParams, GenerateUuidOutput]):
    """Generate a random UUID v4, optionally behind a prefix.

    A fresh identifier is produced on every call, so a test that needs a value
    no earlier run can collide with can mint one here.
    """

    params_model = GenerateUuidParams
    output_model = GenerateUuidOutput

    async def execute(
        self,
        params: GenerateUuidParams,
        context: "StepContext",
        definition: StepDefinition,
    ) -> StepOutput[GenerateUuidOutput]:
        value = f"{params.prefix}{uuid.uuid4()}"
        return StepOutput(value=GenerateUuidOutput(uuid=value))

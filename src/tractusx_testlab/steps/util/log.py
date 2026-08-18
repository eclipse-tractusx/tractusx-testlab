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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""util/log step — surface a resolved value while authoring a test."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepValue

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


def _render(value: Any) -> str:
    """Render *value* for human reading, pretty-printing dicts and lists."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    return str(value)


class LogParams(StepParams):
    """Input contract of ``util/log``."""

    value: Any = Field(
        default=None,
        description="The value to show — typically a '${{ }}' expression.",
    )
    message: str = Field(
        default="",
        description="Label printed before the value; defaults to the step id.",
    )


class LogOutput(StepValue[Any]):
    """The logged value, passed through unchanged."""


@step("util/log")
class LogStep(BaseStep[LogParams, LogOutput]):
    """Write a resolved value to stdout and the run log.

    An authoring aid for inspecting what an expression resolved to; it asserts
    nothing and always passes.  The value is echoed to stdout because the run
    report prints only step names, statuses, and errors.
    """

    params_model = LogParams
    output_model = LogOutput

    async def execute(
        self, params: LogParams, context: StepContext, definition: StepDefinition,
    ) -> StepOutput[LogOutput]:
        label = params.message or getattr(definition, "id", None) or "log"
        rendered = _render(params.value)

        # Through the logger, so the message reaches the JSON-lines log file
        # and the SSE stream the IDE reads. `print` put it on stdout alone.
        logger.info("[log] %s: %s", label, rendered)
        logger.info("%s: %s", label, rendered)

        return StepOutput(value=LogOutput(params.value))

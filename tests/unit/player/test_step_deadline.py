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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""A step is held to the ``timeout_s`` its script declared.

The field reached the runtime definition and the compiled IR and nothing ever
applied it, so a step that never returned — a contract negotiation against a
connector that answers nothing — ran until CI killed the job. These check the
bound now fires, that it fires as a verdict about the step rather than as an
engine fault, and that a step which declared none is left alone.
"""

from __future__ import annotations

import asyncio

from unittest.mock import MagicMock

from tractusx_testlab.models.authoring.definitions import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.results import ENGINE_FAULT_PREFIX
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.steps.step_contract import (
    BaseStep,
    StepOutput,
    StepParams,
    StepPayload,
)


class _Params(StepParams):
    """Inputs of the steps below: none, deliberately."""


class _Output(StepPayload):
    """Output of the steps below."""

    ok: bool = True


class _NeverFinishingStep(BaseStep[_Params, _Output]):
    """Stands in for an SDK call against a connector that never answers."""

    step_type = "connector/consumer/negotiate"
    params_model = _Params
    output_model = _Output

    async def execute(self, params, context, definition) -> StepOutput[_Output]:
        await asyncio.Event().wait()
        raise AssertionError("unreachable — the event is never set")


class _ImmediateStep(BaseStep[_Params, _Output]):
    """A step that answers at once."""

    step_type = "connector/consumer/negotiate"
    params_model = _Params
    output_model = _Output

    async def execute(self, params, context, definition) -> StepOutput[_Output]:
        return StepOutput(value=_Output())


def _definition(timeout_s: float | None) -> StepDefinition:
    return StepDefinition(uses="connector/consumer/negotiate", timeout_s=timeout_s)


class TestDeclaredTimeout:
    async def test_a_step_that_never_finishes_fails_at_its_deadline(
        self, mock_context: MagicMock
    ) -> None:
        result = await run_step(
            _NeverFinishingStep, _definition(0.05), "negotiate", mock_context
        )

        assert result.status == StepStatus.FAILED
        assert result.error is not None
        assert "did not finish within the 0.05s the script allows it" in result.error

    async def test_the_timeout_is_a_verdict_about_the_step_not_an_engine_fault(
        self, mock_context: MagicMock
    ) -> None:
        """A step the SUT hung is a failure of the SUT, not a defect in testlab."""
        result = await run_step(
            _NeverFinishingStep, _definition(0.05), "negotiate", mock_context
        )

        assert result.error is not None
        assert not result.error.startswith(ENGINE_FAULT_PREFIX)

    async def test_a_step_that_answers_in_time_is_untouched(
        self, mock_context: MagicMock
    ) -> None:
        result = await run_step(_ImmediateStep, _definition(30), "negotiate", mock_context)

        assert result.status == StepStatus.PASSED
        assert result.error is None

    async def test_a_step_without_a_declared_timeout_still_runs(
        self, mock_context: MagicMock
    ) -> None:
        result = await run_step(_ImmediateStep, _definition(None), "negotiate", mock_context)

        assert result.status == StepStatus.PASSED

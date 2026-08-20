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

"""Retry step — re-runs a nested list of steps until they all pass or attempts run out."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.scripting.registry import StepRegistry, step
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepValue

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


# ---------------------------------------------------------------------------
# flow/retry
# ---------------------------------------------------------------------------


class RetryParams(StepParams):
    """Input contract of ``flow/retry``."""

    steps: list[StepDefinition] = Field(
        min_length=1,
        description=(
            "Nested step definitions ('uses', 'with', 'validate', …) — the same "
            "shape used at the top level of a script. A nested step may itself "
            "be 'flow/retry'."
        ),
    )
    max_attempts: int = Field(default=3, ge=1, description="Maximum number of attempts.")
    delay_s: float = Field(default=1, ge=0, description="Seconds to wait between attempts.")


class RetryOutput(StepValue[list[Any]]):
    """The nested steps' outputs, in order, from the attempt that finally passed."""


@step("flow/retry")
class RetryStep(BaseStep[RetryParams, RetryOutput]):
    """Run a nested list of steps, retrying the whole sequence on failure.

    The sequence stops at the first nested failure and the whole sequence is
    re-run, so a step that succeeded in a failed attempt runs again — write
    nested steps to be safe to repeat.
    """

    params_model = RetryParams
    output_model = RetryOutput

    async def execute(
        self, params: RetryParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[RetryOutput]:
        attempt = 1
        results = await _run_sequence(params.steps, context)
        while _has_failure(results) and attempt < params.max_attempts:
            attempt += 1
            await asyncio.sleep(params.delay_s)
            results = await _run_sequence(params.steps, context)

        if _has_failure(results):
            failed = next(r for r in results if r.status == StepStatus.FAILED)
            raise RuntimeError(
                f"Nested steps still failing after {attempt} attempt(s): "
                f"'{failed.step_type}' — {failed.error or 'assertion failed'}"
            )

        return StepOutput(value=RetryOutput([result.output for result in results]))


async def _run_sequence(
    nested_defs: list[StepDefinition], context: StepContext
) -> list[StepResult]:
    """Run each nested step in order, stopping at the first failure."""
    results: list[StepResult] = []
    for idx, nested_def in enumerate(nested_defs):
        step_name = f"retry[{idx}]:{nested_def.uses}"
        # A nested step is resolved by name alone: only the phase runner holds
        # the script's dataspace_version, so a version-specific step is looked
        # up by what it declares rather than skipped for want of a version.
        step_cls = StepRegistry.get_any(nested_def.uses)
        if step_cls is None:
            results.append(
                StepResult(
                    step_name=step_name,
                    step_type=nested_def.uses,
                    status=StepStatus.FAILED,
                    error=f"No implementation found for step type '{nested_def.uses}'",
                )
            )
            break

        result: Any = await context.invoke_step(step_cls, nested_def, step_name, context)
        results.append(result)
        if result.status == StepStatus.FAILED:
            break

    return results


def _has_failure(results: list[StepResult]) -> bool:
    return any(result.status == StepStatus.FAILED for result in results)

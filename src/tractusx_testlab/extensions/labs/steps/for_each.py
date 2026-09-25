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

"""Loop step — runs a nested sequence once for every item of a list. **Experimental.**"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.authoring.registry import StepRegistry, step
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tractusx_testlab.player.execution.context import StepContext

#: The item the loop is running its nested steps for, and its position in the
#: list from 0. In scope only inside the loop's ``steps:``; the compiler
#: refuses them anywhere else (``body_references``).
EACH_ITEM = "each.item"
EACH_INDEX = "each.index"


# ---------------------------------------------------------------------------
# labs/flow/for_each
# ---------------------------------------------------------------------------


class ForEachParams(StepParams):
    """Input contract of ``labs/flow/for_each``."""

    items: list[Any] = Field(
        description=(
            "The values to loop over, usually a list a previous step returned. "
            "An empty list runs nothing and passes."
        ),
    )
    steps: list[StepDefinition] = Field(
        min_length=1,
        description=(
            "Nested step definitions run once per item, in order — the same shape "
            "used at the top level of a test. They read the current item as "
            "'${{ each.item }}' and its position, from 0, as '${{ each.index }}'."
        ),
    )


class ForEachOutput(StepPayload):
    """How many items the loop ran for, and what each run produced."""

    iterations: int = Field(description="Number of items the nested steps ran for.")
    outputs: list[list[Any]] = Field(
        default_factory=list,
        description="Per item, in order, the outputs of the nested steps.",
    )


@step("labs/flow/for_each")
class ForEachStep(BaseStep[ForEachParams, ForEachOutput]):
    """Run a nested list of steps once for every item of a list.

    The nested steps resolve their ``with:`` when they run, not when the loop
    starts, which is what lets them read ``${{ each.item }}``. The loop stops
    at the first nested failure and fails with it; a step that reports an
    outcome instead of failing — a delete answering 404 — keeps it going.
    """

    params_model = ForEachParams
    output_model = ForEachOutput
    #: Handed over unresolved by the runner (``resolve_params``): the nested
    #: steps resolve their own ``with:`` once per item.
    deferred_params = frozenset({"steps"})
    #: What the compiler lets a nested step read that exists nowhere else.
    body_references = frozenset({EACH_ITEM, EACH_INDEX})

    async def execute(
        self, params: ForEachParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[ForEachOutput]:
        outputs: list[list[Any]] = []
        with _loop_scope(context):
            for index, item in enumerate(params.items):
                context.set_variable(EACH_ITEM, item)
                context.set_variable(EACH_INDEX, index)
                results = await _run_sequence(params.steps, index, context)
                failed = next((r for r in results if r.status == StepStatus.FAILED), None)
                if failed is not None:
                    raise RuntimeError(
                        f"Nested step failed for item {index} ({item!r}): "
                        f"'{failed.step_type}' — {failed.error or 'assertion failed'}"
                    )
                outputs.append([result.output for result in results])

        return StepOutput(value=ForEachOutput(iterations=len(outputs), outputs=outputs))


@contextmanager
def _loop_scope(context: StepContext) -> Iterator[None]:
    """Put back whatever ``each.*`` meant before this loop, once it ends.

    A loop nested in another loop's steps rebinds ``each.item`` for its own
    items; the outer loop's remaining steps must read the outer item again.
    Outside every loop the names are unset, so a stray reference fails as
    unresolved instead of reading the last item.
    """
    saved = {
        name: context.get_variable(name)
        for name in (EACH_ITEM, EACH_INDEX)
        if context.has_variable(name)
    }
    try:
        yield
    finally:
        for name in (EACH_ITEM, EACH_INDEX):
            if name in saved:
                context.set_variable(name, saved[name])
            else:
                context.unset_variable(name)


async def _run_sequence(
    nested_defs: list[StepDefinition], index: int, context: StepContext
) -> list[StepResult]:
    """Run each nested step in order for one item, stopping at the first failure."""
    results: list[StepResult] = []
    for idx, nested_def in enumerate(nested_defs):
        step_name = f"each[{index}][{idx}]:{nested_def.uses}"
        # Resolved by name alone, as flow/retry and flow/if do: only the phase
        # runner holds the test's dataspace_version.
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

        result = await context.invoke_step(step_cls, nested_def, step_name, context)
        results.append(result)
        if result.status == StepStatus.FAILED:
            break

    return results

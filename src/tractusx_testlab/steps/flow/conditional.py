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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Conditional step — runs one of two nested sequences depending on a condition."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.scripting.registry import StepRegistry, step
from tractusx_testlab.steps._checks.extraction import extract_path
from tractusx_testlab.steps.assertions import AssertOperator, apply_operator
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

# Version-specific step overrides are not resolvable from within a step body
# (only the script's dataspace_version, held by the phase runner, knows that),
# so nested steps are looked up in the global (version-agnostic) registry.
_ANY_VERSION = ""


# ---------------------------------------------------------------------------
# flow/if
# ---------------------------------------------------------------------------


class Condition(BaseModel):
    """One comparison the branch is decided on.

    Deliberately the same shape a ``validate:`` entry has — a value, an optional
    path into it, an operator and something to compare against — so a script
    author moves between asserting on a fact and branching on it without
    learning a second way to state one.
    """

    model_config = ConfigDict(extra="forbid")

    input: Any = Field(
        default=None, description="The value to test, usually a previous step's output."
    )
    path: str = Field(
        default="",
        description="Dot-notation path into the input, e.g. 'content.state'; empty tests it whole.",
    )
    operator: AssertOperator = Field(
        default="not_null", description="Comparison applied to the value."
    )
    value: Any = Field(
        default=None,
        description="What the value is compared against; unused by unary operators.",
    )

    def holds(self) -> bool:
        """Whether this comparison is satisfied."""
        actual = extract_path(self.input, self.path) if self.path else self.input
        passed, _ = apply_operator(self.operator, actual, self.value)
        return passed


class IfParams(StepParams):
    """Input contract of ``flow/if``.

    ``validate_by_name`` is off because ``else`` is a Python keyword and cannot
    be a field name: the attribute has to be called something else.  Leaving the
    attribute name bindable would make ``otherwise:`` a second accepted spelling
    of ``else:``, which is the one thing this contract does not allow.  ``else``
    is the script keyword; ``otherwise`` is only how Python spells the field.
    """

    model_config = ConfigDict(extra="forbid", validate_by_name=False)

    conditions: list[Condition] = Field(
        min_length=1,
        description="Comparisons evaluated before a branch is chosen.",
    )
    match: Literal["all", "any"] = Field(
        default="all",
        description="Whether every condition must hold ('all') or just one ('any').",
    )
    then: list[StepDefinition] = Field(
        min_length=1,
        description=(
            "Nested step definitions run when the condition holds — the same "
            "shape used at the top level of a script."
        ),
    )
    otherwise: list[StepDefinition] = Field(
        default_factory=list,
        validation_alias="else",
        serialization_alias="else",
        description=(
            "Nested step definitions run when it does not; omitted means the "
            "step does nothing in that case."
        ),
    )


class IfOutput(StepPayload):
    """Which way the step went, and what the branch it took produced."""

    condition_result: bool = Field(description="How the condition evaluated.")
    branch_taken: Literal["then", "else", "none"] = Field(
        description="The branch that ran; 'none' when the condition was false and "
        "no 'else' was given."
    )
    outputs: list[Any] = Field(
        default_factory=list, description="Outputs of the nested steps that ran, in order."
    )


@step("flow/if")
class IfStep(BaseStep[IfParams, IfOutput]):
    """Run one of two nested sequences depending on a set of conditions.

    A step's own ``if:`` decides whether that one step runs; this decides
    between two sequences, and says afterwards which one it picked — a script
    asserting on ``branch_taken`` can prove the flow went the way it meant to,
    which "the steps in the other branch were skipped" never quite shows.

    The conditions are evaluated once, before either branch starts, using the
    same comparisons a ``validate:`` block asserts with.
    """

    params_model = IfParams
    output_model = IfOutput

    async def execute(
        self, params: IfParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[IfOutput]:
        outcomes = [condition.holds() for condition in params.conditions]
        condition_result = all(outcomes) if params.match == "all" else any(outcomes)
        branch = params.then if condition_result else params.otherwise

        if not branch:
            # ``outputs`` is set even though it is empty: "nothing ran" is a
            # result, and a script reading it should not find the key missing.
            return StepOutput(
                value=IfOutput(
                    condition_result=condition_result, branch_taken="none", outputs=[]
                )
            )

        label: Literal["then", "else"] = "then" if condition_result else "else"
        results = await _run_sequence(branch, label, context)

        failed = next((r for r in results if r.status == StepStatus.FAILED), None)
        if failed is not None:
            raise RuntimeError(
                f"Nested step failed in the '{label}' branch: "
                f"'{failed.step_type}' — {failed.error or 'assertion failed'}"
            )

        return StepOutput(
            value=IfOutput(
                condition_result=condition_result,
                branch_taken=label,
                outputs=[result.output for result in results],
            )
        )


async def _run_sequence(
    nested_defs: list[StepDefinition], label: str, context: StepContext
) -> list[StepResult]:
    """Run each nested step in order, stopping at the first failure."""
    results: list[StepResult] = []
    for idx, nested_def in enumerate(nested_defs):
        step_name = f"if.{label}[{idx}]:{nested_def.uses}"
        step_cls = StepRegistry.get(nested_def.uses, _ANY_VERSION)
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

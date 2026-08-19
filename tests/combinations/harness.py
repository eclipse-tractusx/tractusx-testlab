################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""Run a sequence of steps the way the player runs a phase.

The point of these tests is the wiring *between* steps, so the harness must not
reimplement it: it calls the same ``run_step`` and ``store_step_outputs`` the
phase runner calls, and reads the namespace from the same table. A harness that
published outputs its own way would pass while the player failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job, StepDefinition, StepStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution._step_outputs import store_step_outputs
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.phase import _PHASE_TO_NAMESPACE
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.services.instances import ServiceManager

# Nested steps are looked up version-agnostically, and so is everything here:
# these tests are about the wiring, not about version overrides.
_ANY_VERSION = ""


@dataclass(frozen=True)
class Outcome:
    """What a run produced — per step, and in the variables it left behind."""

    results: list[StepResult]
    variables: dict[str, Any]

    @property
    def passed(self) -> bool:
        return all(result.status == StepStatus.PASSED for result in self.results)

    @property
    def failures(self) -> list[StepResult]:
        return [r for r in self.results if r.status == StepStatus.FAILED]

    def result(self, step_id: str) -> StepResult:
        """The result of the step with this ``id``."""
        for result in self.results:
            if result.step_name == step_id:
                return result
        raise AssertionError(
            f"No step named {step_id!r} ran. Ran: {[r.step_name for r in self.results]}"
        )

    def output(self, step_id: str) -> Any:
        """What the step with this ``id`` returned."""
        return self.result(step_id).output

    def error(self, step_id: str) -> str | None:
        """Why the step with this ``id`` failed, if it did."""
        return self.result(step_id).error

    def assertion_messages(self, step_id: str) -> list[str]:
        """Every assertion message the step recorded, passing or not."""
        return [a.message or "" for a in self.result(step_id).assertions]


class Harness:
    """A live ``StepContext`` and a way to run steps through it in order.

    Steps are given as the mappings a TCK author writes — ``uses``, ``with``,
    ``returns``, ``validate`` — so a test reads like the YAML it stands for.
    """

    def __init__(self, context: StepContext) -> None:
        self.context = context

    async def run(self, *steps: dict, phase: str = "execution") -> Outcome:
        """Run *steps* in order, publishing each one's returns before the next.

        Execution does **not** stop at the first failure: a combination test
        usually wants to see what the rest of the chain then did with a missing
        value, which stopping would hide.
        """
        namespace = _PHASE_TO_NAMESPACE[phase]
        results: list[StepResult] = []

        for index, raw in enumerate(steps):
            step_def = StepDefinition.model_validate(raw)
            step_id = step_def.id or f"{phase}[{index}]"
            step_cls = StepRegistry.get(step_def.uses, _ANY_VERSION)
            if step_cls is None:
                raise AssertionError(
                    f"Step {step_def.uses!r} is not registered — a combination test "
                    "cannot say anything about a step the engine does not have."
                )

            result = await run_step(step_cls, step_def, step_id, self.context)
            store_step_outputs(step_def, result, self.context, step_namespace=namespace)
            results.append(result)

        return Outcome(results=results, variables=self.context.variables)

    def seed(self, **variables: Any) -> None:
        """Put values in the context the way ``env:`` and the player would."""
        for name, value in variables.items():
            self.context.set_variable(name, value)


def build_context(
    services: ServiceManager | None = None,
    config: TestlabConfig | None = None,
) -> StepContext:
    """A real ``StepContext``, not a mock — variable resolution is under test."""
    return StepContext(
        services=services if services is not None else ServiceManager(),
        job=Job(job_id="combination-test"),
        config=config if config is not None else TestlabConfig(),
    )

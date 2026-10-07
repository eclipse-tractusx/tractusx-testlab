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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.


"""What a flow step's sub-steps checked, reported as the flow step's own checks.

A sub-step of ``flow/if``, ``flow/retry`` or ``labs/flow/for_each`` runs through
the same runner as a top-level step, and its ``validate:`` block is evaluated —
but only the phase runner publishes a result, and it publishes the flow step's.
The sub-steps' checks used to stop at the flow step, which kept their outputs
and dropped the rest: a check that passed was never reported, and one that
failed was reported as "assertion failed", without saying which.

The flow step now hands them on. Each check keeps its place — the path of
sub-steps it was evaluated on — so a reader, and the trace, can tell them apart
from the flow step's own.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.primitives.exceptions import ExecutionError
from tractusx_testlab.models.runtime.results import (
    ENGINE_FAULT_PREFIX,
    AssertionResult,
    StepResult,
)


@dataclass(frozen=True)
class NestedChecks:
    """The checks a flow step's sub-steps evaluated, and how many they declared."""

    checks: list[AssertionResult] = field(default_factory=list)
    declared: int = 0

    def __add__(self, other: NestedChecks) -> NestedChecks:
        return NestedChecks(self.checks + other.checks, self.declared + other.declared)


def trace_key(definition: StepDefinition) -> str:
    """What a sub-step is called in a check's path — the name its calls are traced under."""
    return definition.id or definition.uses.rsplit("/", 1)[-1]


def nested_checks(
    definitions: Sequence[StepDefinition],
    results: Sequence[StepResult],
    prefix: Sequence[str] = (),
) -> NestedChecks:
    """The checks of the sub-steps that ran, each under the sub-step it belongs to.

    *results* is positional: a sequence stops at its first failure, so it holds
    one entry per sub-step that ran, in order. A sub-step that is itself a flow
    step already carries its own sub-steps' checks, each with a path of its own;
    that path is kept, under the sub-step's name.
    """
    checks: list[AssertionResult] = []
    declared = 0
    for definition, result in zip(definitions, results, strict=False):
        path = [*prefix, trace_key(definition)]
        declared += len(definition.assertions or []) + result.nested_declared
        checks += [
            check.model_copy(
                update={
                    "step_path": [*path, *check.step_path],
                    "step_cac": check.step_cac or list(result.cac),
                }
            )
            for check in result.assertions
        ]
    return NestedChecks(checks, declared)


class NestedStepFailed(ExecutionError):
    """A sub-step failed, and with it the flow step that ran it.

    A verdict about whatever the sub-step's failure was about — not an engine
    fault, which is what the ``RuntimeError`` raised before this made of every
    failing check inside a branch. It carries the sub-steps' checks, so the one
    that failed is reported by name rather than as "assertion failed".
    """

    def __init__(self, message: str, failed: StepResult, nested: NestedChecks) -> None:
        super().__init__(message)
        self.nested = nested
        self.origin = failed.error_origin or (
            "engine" if (failed.error or "").startswith(ENGINE_FAULT_PREFIX) else "sut"
        )
        self.code = failed.error_code


def first_failure(results: Sequence[StepResult]) -> StepResult | None:
    """The sub-step that stopped the sequence, if one did."""
    return next((result for result in results if result.status == StepStatus.FAILED), None)

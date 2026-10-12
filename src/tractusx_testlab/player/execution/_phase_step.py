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

"""Running one top-level step of a phase: announce it, honour its ``if:``, run it.

Split from ``phase`` so the phase loop reads as a loop: the gate, the step's
frame (``player.checkpoints``), the step, and whether the phase goes on.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.models import StepStatus
from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution._not_run import missing_step_result, skipped_result
from tractusx_testlab.player.loading.resolver import try_resolve_params
from tractusx_testlab.security.credentials import credential_carriers
from tractusx_testlab.steps.conditions import ConditionEvaluator

if TYPE_CHECKING:
    from tractusx_testlab.authoring.test import Test
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.player.execution.monitor import ExecutionMonitor
    from tractusx_testlab.player.execution.phase import PhaseConfig
    from tractusx_testlab.player.jobs import JobManager


class FailurePolicy(Enum):
    """Determines behavior on step failure."""

    STOP = auto()
    CONTINUE = auto()


async def run_phase_step(
    test: Test,
    step_idx: int,
    step_def: Any,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager | None,
    config: PhaseConfig,
    results: list[StepResult],
) -> bool:
    """Run the phase's step *step_idx*; returns whether the phase stops on it."""
    step_name = format_step_name(
        test.definition.id, step_idx, step_def.uses, config.phase_label, step_def.id
    )
    # Resolved before the event rather than inside the runner: ``step.start``
    # reports what the step is about to be given, not the ``${{ }}`` it was
    # written with. ``None`` (a reference naming nothing) publishes the block
    # as written and leaves the failure to the runner. A flow step's nested
    # steps stay as written: each resolves its own ``with:`` when it runs.
    step_cls = StepRegistry.get(step_def.uses, test.dataspace_version)
    deferred: frozenset[str] = getattr(step_cls, "deferred_params", frozenset())
    carriers = credential_carriers(step_cls)
    params = try_resolve_params(step_def.with_ or {}, context, deferred, carriers)
    monitor.on_step_started(
        job_id,
        test.definition.id,
        step_def.id,
        step_idx,
        step_def.uses,
        step_name,
        config.phase_label,
        step_def.with_ if params is None else params,
    )

    if config.use_pause_gate and jobs is not None:
        jobs.set_current_step(job_id, step_name)

    if config.evaluate_conditions and not ConditionEvaluator.should_run(
        step_def.if_condition,
        results,
        context,
    ):
        skipped = skipped_result(step_name, step_def.uses, config.phase)
        # A skipped step still names its CACs: ones this run did not verify.
        skipped.cac = list(step_def.cac or context.test_cac)
        context.steps.record(context.step_namespace, step_def.id, StepStatus.SKIPPED)
        results.append(skipped)
        monitor.on_step_completed(job_id, test.definition.id, step_def.id, skipped)
        # A step whose `if:` said no must not then run: recording SKIPPED and
        # executing it anyway is the one outcome the condition rules out.
        return False

    return await _resolve_and_run_step(
        test, step_def, step_name, context, job_id, monitor, config, results, params
    )


async def _resolve_and_run_step(
    test: Test,
    step_def: Any,
    step_name: str,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    config: PhaseConfig,
    results: list[StepResult],
    params: dict[str, Any] | None = None,
) -> bool:
    """Resolve step class, execute, store outputs. Returns True if phase should abort."""
    from tractusx_testlab.player.execution._step_outputs import run_and_publish

    step_cls = StepRegistry.get(step_def.uses, test.dataspace_version)
    if step_cls is None:
        missing = missing_step_result(step_name, step_def.uses, config.phase)
        context.steps.record_result(context.step_namespace, step_def.id, missing)
        results.append(missing)
        monitor.on_step_completed(job_id, test.definition.id, step_def.id, missing)
        return config.failure_policy == FailurePolicy.STOP

    # Only now does the step run: a checkpoint it does not ask for itself is
    # asked here, not at ``step.start`` — a step whose `if:` said no, or whose
    # type is missing, was never asked.
    context.checkpoints.begin()
    step_result = await run_and_publish(step_cls, step_def, step_name, context, params)
    step_result.phase = config.phase
    results.append(step_result)
    monitor.on_step_completed(job_id, test.definition.id, step_def.id, step_result)

    return step_result.status == StepStatus.FAILED and config.failure_policy == FailurePolicy.STOP


def steps_for_phase(test: Test, phase: StepPhase) -> list:
    """Return the step definitions list for the given phase."""
    if phase == StepPhase.SETUP:
        return test.definition.setup
    if phase == StepPhase.TEARDOWN:
        return test.definition.teardown
    return test.definition.execution


def format_step_name(
    test_name: str, idx: int, step_type: str, phase_label: str, step_id: str | None = None
) -> str:
    """Format a step identifier using step id when available, index otherwise."""
    step_ref = step_id if step_id else f"{idx}"
    if phase_label == "execution":
        return f"{test_name}[{step_ref}]:{step_type}"
    return f"{test_name}[{phase_label}:{step_ref}]:{step_type}"

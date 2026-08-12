#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Shared per-step execution loop used by all phase runners."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from tractusx_testlab.models import ScriptStatus, StepStatus
from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.scripting.script import TestScript
from tractusx_testlab.steps.conditions import ConditionEvaluator

# Maps internal phase_label to the expression namespace (e.g. "steps.ID.field")
_PHASE_TO_NAMESPACE: dict[str, str] = {
    "setup": "setup",
    "main": "steps",
    "cleanup": "teardown",
}


class FailurePolicy(Enum):
    """Determines behavior on step failure."""

    STOP = auto()
    CONTINUE = auto()


@dataclass(frozen=True)
class PhaseConfig:
    """Configuration for a phase execution loop."""

    phase: StepPhase
    phase_label: str
    failure_policy: FailurePolicy
    evaluate_conditions: bool
    use_pause_gate: bool
    store_outputs: bool


async def _run_phase(
    script: TestScript,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager | None,
    config: PhaseConfig,
) -> tuple[list[StepResult], ScriptStatus]:
    """Execute a sequence of steps according to the given phase configuration."""
    steps_source = _get_steps_for_phase(script, config.phase)
    results: list[StepResult] = []

    for step_idx, step_def in enumerate(steps_source):
        await _handle_pause_gate(jobs, job_id, config)

        step_name = _format_step_name(script.definition.id, step_idx, step_def.uses, config.phase_label, step_def.id)
        monitor.on_step_started(
            job_id,
            script.definition.id,
            step_def.id,
            step_idx,
            step_def.uses,
            step_name,
            config.phase_label,
        )

        if config.use_pause_gate and jobs is not None:
            jobs.set_current_step(job_id, step_name)

        if config.evaluate_conditions and not ConditionEvaluator.should_run(
            step_def.if_condition, results, context,
        ):
            skipped = _make_skipped_result(step_name, step_def.uses, config.phase)
            results.append(skipped)
            monitor.on_step_completed(job_id, script.definition.id, step_def.id, skipped)
            # A step whose `if:` said no must not then run: recording SKIPPED and
            # executing it anyway is the one outcome the condition rules out.
            continue

        failed = await _resolve_and_run_step(
            script, step_def, step_name, context, job_id, monitor, config, results,
        )
        if failed:
            return results, ScriptStatus.FAILED

    return results, ScriptStatus.COMPLETED


async def _handle_pause_gate(
    jobs: JobManager | None, job_id: str, config: PhaseConfig,
) -> None:
    """Wait on the pause gate if configured."""
    if config.use_pause_gate and jobs is not None:
        await jobs.get_pause_event(job_id).wait()


async def _resolve_and_run_step(
    script: TestScript,
    step_def: Any,
    step_name: str,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    config: PhaseConfig,
    results: list[StepResult],
) -> bool:
    """Resolve step class, execute, store outputs. Returns True if phase should abort."""
    from tractusx_testlab.player.execution.step_runner import run_step, store_step_outputs

    step_cls = StepRegistry.get(step_def.uses, script.dataspace_version)
    if step_cls is None:
        missing = _make_missing_step_result(step_name, step_def.uses, config.phase)
        results.append(missing)
        monitor.on_step_completed(job_id, script.definition.id, step_def.id, missing)
        return config.failure_policy == FailurePolicy.STOP

    step_result = await run_step(step_cls, step_def, step_name, context)
    step_result.phase = config.phase
    results.append(step_result)
    monitor.on_step_completed(job_id, script.definition.id, step_def.id, step_result)

    if config.store_outputs:
        step_namespace = _PHASE_TO_NAMESPACE.get(config.phase_label)
        store_step_outputs(step_def, step_result, context, step_namespace=step_namespace)

    return step_result.status == StepStatus.FAILED and config.failure_policy == FailurePolicy.STOP


def _get_steps_for_phase(script: TestScript, phase: StepPhase) -> list:
    """Return the step definitions list for the given phase."""
    if phase == StepPhase.SETUP:
        return script.definition.setup
    if phase == StepPhase.TEARDOWN:
        return script.definition.teardown
    return script.definition.execution


def _format_step_name(script_name: str, idx: int, step_type: str, phase_label: str, step_id: str | None = None) -> str:
    """Format a step identifier using step id when available, index otherwise."""
    step_ref = step_id if step_id else f"{idx}"
    if phase_label == "main":
        return f"{script_name}[{step_ref}]:{step_type}"
    return f"{script_name}[{phase_label}:{step_ref}]:{step_type}"


def _make_skipped_result(step_name: str, step_type: str, phase: StepPhase) -> StepResult:
    """Create a StepResult for a condition-skipped step."""
    return StepResult(
        step_name=step_name,
        step_type=step_type,
        phase=phase,
        status=StepStatus.SKIPPED,
    )


def _make_missing_step_result(step_name: str, step_type: str, phase: StepPhase) -> StepResult:
    """Create a StepResult for a step with no registered implementation."""
    return StepResult(
        step_name=step_name,
        step_type=step_type,
        phase=phase,
        status=StepStatus.FAILED,
        error=f"No implementation found for step type '{step_type}'",
    )

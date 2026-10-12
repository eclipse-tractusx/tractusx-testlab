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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.


"""Running a test's steps, one phase at a time.

Setup, execution and teardown differ in four decisions — whether a failure
stops the phase, whether ``if:`` conditions are honoured, whether the pause
gate applies, and whether outputs are published — and in nothing else.  Those
four are :class:`PhaseConfig`, and the three named runners below are the three
settings of it, so a change to how a step is run cannot reach one phase and
miss another.
"""

from __future__ import annotations

from dataclasses import dataclass

from tractusx_testlab.authoring.test import Test
from tractusx_testlab.models import TestStatus
from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution._phase_step import (
    FailurePolicy,
    run_phase_step,
    steps_for_phase,
)
from tractusx_testlab.player.execution._reporters import bind_reporters
from tractusx_testlab.player.execution._step_outcomes import failure_origin
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.jobs import JobManager

# Maps a phase label to the expression namespace (e.g. "execution.ID.field").
#
# The namespace is the phase's own name, for every phase. It used to differ for
# the execution phase, whose steps published under ``steps.`` while authors —
# and the syntax reference (§5.2), and the IDE that emits from it — wrote
# ``${{ execution.<id>.<field> }}``. Nothing reported the mismatch: an
# unresolvable reference is left as its own template text, so the *literal*
# string ``${{ execution.mint.uuid }}`` was passed to the next step as if it
# were the value.
_PHASE_TO_NAMESPACE: dict[str, str] = {
    "setup": "setup",
    "execution": "execution",
    "teardown": "teardown",
}


@dataclass(frozen=True)
class PhaseConfig:
    """Configuration for a phase execution loop."""

    phase: StepPhase
    phase_label: str
    failure_policy: FailurePolicy
    evaluate_conditions: bool
    use_pause_gate: bool
    store_outputs: bool


async def run_phase(
    test: Test,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager | None,
    config: PhaseConfig,
) -> tuple[list[StepResult], TestStatus]:
    """Execute a sequence of steps according to the given phase configuration."""
    steps_source = steps_for_phase(test, config.phase)
    results: list[StepResult] = []

    # A call is published while the step that made it is still running, and this
    # is the layer that knows which job and which test it belongs to. The step
    # runner adds the step, including for the steps nested inside a flow step,
    # which run on this same context (_reporters).
    bind_reporters(context, monitor, job_id, test.definition.id, config.phase_label)
    context.bind_test_cac(getattr(test.definition, "cac", None))
    context.bind_step_namespace(
        _PHASE_TO_NAMESPACE.get(config.phase_label) if config.store_outputs else None
    )

    for step_idx, step_def in enumerate(steps_source):
        if config.use_pause_gate and jobs is not None:
            await context.hold.gate(jobs, job_id)

        # The step runs in a frame of its own: which run of it this is, and the
        # checkpoint it is, go on everything it publishes (player.checkpoints).
        with context.checkpoints.step(test.definition.id, (config.phase_label, step_idx)):
            failed = await run_phase_step(
                test, step_idx, step_def, context, job_id, monitor, jobs, config, results
            )
        if failed:
            # What it kept from running follows from it (resolver.origin_of).
            context.steps.record_stop(failure_origin(results[-1]))
            return results, TestStatus.FAILED

    return results, TestStatus.COMPLETED


# ---------------------------------------------------------------------------
# The three phases
# ---------------------------------------------------------------------------

#: Setup and execution are run identically — the label they report under and the
#: steps they read are the whole difference. Spelled out rather than shared
#: through a splat so each phase's four decisions are readable in one place.
SETUP = PhaseConfig(
    phase=StepPhase.SETUP,
    phase_label="setup",
    failure_policy=FailurePolicy.STOP,
    evaluate_conditions=True,
    use_pause_gate=True,
    store_outputs=True,
)

EXECUTION = PhaseConfig(
    phase=StepPhase.EXECUTION,
    phase_label="execution",
    failure_policy=FailurePolicy.STOP,
    evaluate_conditions=True,
    use_pause_gate=True,
    store_outputs=True,
)

#: Teardown is the phase that must happen regardless: it runs after a failure,
#: ignores ``if:`` and cannot be paused. It publishes under ``teardown.`` like
#: the others: a delete loop reads the ids a query step before it found.
TEARDOWN = PhaseConfig(
    phase=StepPhase.TEARDOWN,
    phase_label="teardown",
    failure_policy=FailurePolicy.CONTINUE,
    evaluate_conditions=False,
    use_pause_gate=False,
    store_outputs=True,
)


async def run_setup(
    test: Test,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager,
) -> tuple[list[StepResult], TestStatus]:
    """Run the test's setup steps, stopping at the first failure."""
    return await run_phase(test, context, job_id, monitor, jobs, SETUP)


async def run_execution(
    test: Test,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager,
) -> tuple[list[StepResult], TestStatus]:
    """Run the test's main steps, stopping at the first failure."""
    return await run_phase(test, context, job_id, monitor, jobs, EXECUTION)


async def run_teardown(
    test: Test,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager | None = None,
) -> list[StepResult]:
    """Run the test's teardown steps, whatever happened before them."""
    results, _ = await run_phase(test, context, job_id, monitor, jobs, TEARDOWN)
    return results

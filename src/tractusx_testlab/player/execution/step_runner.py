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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Step-level execution helpers — run individual steps, evaluate assertions, store outputs."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from itertools import count
from typing import Any

from tractusx_testlab.logging import wire
from tractusx_testlab.models import EngineError, ScriptStatus, StepStatus, TestLabError
from tractusx_testlab.models.runtime.results import (
    ENGINE_FAULT_PREFIX,
    AssertionResult,
    ScriptResult,
    StepResult,
)
from tractusx_testlab.player.execution._deadline import invoke_within_deadline
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.execution.phase import (
    run_execution,
    run_setup,
    run_teardown,
)
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.player.loading.resolver import resolve_params
from tractusx_testlab.scripting.script import TestScript
from tractusx_testlab.steps.assertions import AssertionEngine

logger = logging.getLogger(__name__)


def _resolve_assertions(assertions: list[Any], context: StepContext) -> list[Any]:
    """Resolve ``${{ … }}`` references in each assertion's ``with:`` block.

    A ``validate:`` entry compares against things the run produced — a value an
    earlier step returned, a schema declared in ``env`` — and writes them the
    way every other value is written. Only the step's own ``with:`` used to be
    resolved, so those references reached the comparison as their own template
    text: the check then failed against a string nobody wrote, and said so in a
    message that read like a real mismatch.

    ``input`` is unaffected: it names one of the step's returns and carries no
    reference to resolve.
    """
    return [
        assertion.model_copy(update={"with_": resolve_params(assertion.with_ or {}, context)})
        for assertion in assertions
    ]


async def run_step(
    step_cls: type,
    step_def: Any,
    step_name: str,
    context: StepContext,
    params: dict[str, Any] | None = None,
) -> StepResult:
    """Execute a single step, evaluate its assertions, and decide its outcome.

    *params* is the ``with:`` block already resolved against *context* — the
    phase runner resolves it to publish it on the ``step.start`` event, and
    passing it on means the same references are read once rather than twice.
    ``None`` means "not resolved yet", either because a caller had no reason to
    (a flow step running a nested one) or because resolution failed; either way
    it is resolved below, inside the guard.

    This is a supervisory boundary, so it catches broadly on purpose: a step
    that raises must fail *that step*, not abort the TCK. It used to catch five
    exception types by name, which meant a ``requests.RequestException`` — the
    single most likely thing to happen when testing a remote SUT — escaped and
    killed the whole run at step 3 of 40, losing the teardown with it.

    Catching broadly is only safe if the outcome is then classified, and that is
    the second half: an ``EngineError``, or any exception TestLab did not raise
    deliberately, is a defect in the engine rather than a verdict about the SUT.
    """
    step_instance = step_cls()
    started_at = datetime.now(UTC)

    # Bound here rather than at the composition root so that every context which
    # reaches a step can run a nested one — including the contexts built directly
    # by tests. See contracts.StepInvoker for why a flow step is handed the
    # runner instead of importing it.
    context.bind_invoker(run_step)

    # The SDK's traffic is the traffic worth seeing and the engine never makes
    # it. Both it and the engine's own calls are recorded for the duration of
    # this block, under the step's name, and each one is published as it comes
    # back rather than all of them once the step is over (logging.wire).
    calls = count(1)

    def report(call: Any) -> None:
        context.report_call(step_def.uses, getattr(step_def, "id", None), next(calls), call)

    with wire.recording(step_name, on_call=report) as recorder:
        result = await _run_step_guarded(
            step_instance, step_def, step_name, context, started_at, params
        )
    wire.attach_to(result, recorder)
    return result


async def _run_step_guarded(
    step_instance: Any,
    step_def: Any,
    step_name: str,
    context: StepContext,
    started_at: datetime,
    params: dict[str, Any] | None = None,
) -> StepResult:
    """Run one step and classify its outcome; never raises."""
    inputs: dict[str, Any] | None = None
    try:
        # Inside the guard: resolving a step's parameters is part of running it,
        # and an unresolvable reference must fail that step rather than escape
        # and take the run down with it. A caller that already resolved them
        # hands them over; one that could not, or never tried, passes ``None``
        # and the same call is made here.
        if params is None:
            params = resolve_params(step_def.with_ or {}, context)
        # What the step was actually given, once every ``${{ ... }}`` was
        # resolved. A step that failed on what a reference resolved to cannot be
        # debugged from the script, which only says which reference was written.
        inputs = dict(params)

        output = await invoke_within_deadline(step_instance, step_def, params, context)

        assertion_results: list[AssertionResult] = []
        if step_def.assertions:
            assertion_results = [
                AssertionResult.model_validate(ar.model_dump())
                for ar in AssertionEngine.evaluate(
                    _resolve_assertions(step_def.assertions, context),
                    output,
                )
            ]

        finished_at = datetime.now(UTC)
        failed = AssertionEngine.has_hard_failure(assertion_results)

        return StepResult(
            step_name=step_name,
            step_type=step_def.uses,
            status=StepStatus.FAILED if failed else StepStatus.PASSED,
            started_at=started_at,
            finished_at=finished_at,
            duration_s=(finished_at - started_at).total_seconds(),
            inputs=inputs,
            output=output.value,
            request=output.request,
            response=output.response,
            assertions=assertion_results,
        )
    except Exception as exc:
        finished_at = datetime.now(UTC)
        engine_fault = isinstance(exc, EngineError) or not isinstance(
            exc, TestLabError | ValueError
        )
        if engine_fault:
            logger.exception("Engine fault while running step %s", step_name)
        return StepResult(
            step_name=step_name,
            step_type=step_def.uses,
            status=StepStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_s=(finished_at - started_at).total_seconds(),
            # ``None`` when resolution itself failed, which is the one case
            # where the step was never given anything at all.
            inputs=inputs,
            error=f"{ENGINE_FAULT_PREFIX if engine_fault else ''}{exc}",
            # An error that named itself keeps its name and its evidence: a
            # message is what a person reads, and the code and the comparison
            # behind it are what the IDE renders and what a report groups by
            # (ADR-0016). Read off the exception rather than declared per raise
            # site, so an error that has nothing extra to say costs nothing.
            error_code=getattr(exc, "code", None),
            error_context=getattr(exc, "diagnostics", None),
        )


async def run_script(
    script: TestScript,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager,
) -> ScriptResult:
    """Execute all steps in a script sequentially (setup → main → teardown)."""
    script_start = datetime.now(UTC)

    step_results: list[StepResult] = []
    setup_results, setup_status = await run_setup(
        script,
        context,
        job_id,
        monitor,
        jobs,
    )
    if setup_status == ScriptStatus.FAILED:
        script_status = ScriptStatus.FAILED
    else:
        step_results, script_status = await run_execution(
            script,
            context,
            job_id,
            monitor,
            jobs,
        )

    teardown_results = await run_teardown(
        script,
        context,
        job_id,
        monitor,
    )

    script_end = datetime.now(UTC)
    all_step_results = setup_results + step_results + teardown_results

    summary = AssertionEngine.build_summary(
        all_step_results, declared=_declared_assertions(script, all_step_results)
    )

    # Checks that were asked for and did not run mean the result describes less
    # than the script claimed to verify. The engine evaluates assertions one for
    # one, so this should be unreachable — which is exactly why it is measured
    # rather than trusted: the defect this whole review started from was
    # assertions going missing between the script and the result.
    if summary.unevaluated:
        script_status = ScriptStatus.FAILED

    return ScriptResult(
        script_id=script.definition.id,
        script_name=script.name,
        dataspace_version=script.dataspace_version,
        status=script_status,
        execution=all_step_results,
        started_at=script_start,
        finished_at=script_end,
        total_duration_s=(script_end - script_start).total_seconds(),
        assertion_summary=summary,
    )


def _declared_assertions(script: TestScript, results: list[StepResult]) -> int:
    """Count the assertions the steps that actually ran had asked for.

    Steps skipped by ``if:`` are excluded: a check that was never reached was
    not dropped, it was correctly not applicable.
    """
    ran = {result.step_type for result in results if result.status is not StepStatus.SKIPPED}
    return sum(
        len(step.assertions or [])
        for phase in (
            script.definition.setup,
            script.definition.execution,
            script.definition.teardown,
        )
        for step in phase
        if step.uses in ran
    )

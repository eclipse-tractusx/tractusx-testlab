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

"""Step-level execution helpers — run individual steps, evaluate assertions, store outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tractusx_testlab.models import ScriptStatus, StepStatus
from tractusx_testlab.models.runtime.results import (
    AssertionResult,
    ScriptResult,
    StepResult,
)
from tractusx_testlab.player.execution._helpers import (
    register_script_services,
    seed_script_defaults,
)
from tractusx_testlab.player.execution._phase_runners import (
    execute_main_steps,
    execute_setup_steps,
    execute_teardown_steps,
)
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.player.loading.resolver import resolve_params
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.scripting.script import TestScript
from tractusx_testlab.steps.assertions import AssertionEngine


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
        assertion.model_copy(
            update={"with_": resolve_params(assertion.with_ or {}, context)}
        )
        for assertion in assertions
    ]


async def run_step(
    step_cls: type, step_def: Any, step_name: str, context: StepContext,
) -> StepResult:
    """Execute a single step and evaluate its assertions."""
    step_instance = step_cls()
    params = resolve_params(step_def.with_ or {}, context)
    started_at = datetime.now(UTC)

    try:
        output = await step_instance.invoke(params, context, step_def)

        assertion_results: list[AssertionResult] = []
        if step_def.validate:
            assertion_results = [
                AssertionResult.model_validate(ar.model_dump())
                for ar in AssertionEngine.evaluate(
                    _resolve_assertions(step_def.validate, context),
                    output,
                    context.variables,
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
            output=output.value,
            request=output.request,
            response=output.response,
            assertions=assertion_results,
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        finished_at = datetime.now(UTC)
        return StepResult(
            step_name=step_name,
            step_type=step_def.uses,
            status=StepStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_s=(finished_at - started_at).total_seconds(),
            error=str(exc),
        )


def store_step_outputs(
    step_def: Any, step_result: StepResult, context: StepContext,
    *, step_namespace: str | None = None,
) -> None:
    """Persist step outputs into context variables when returns is configured.

    Stores each return field both flat (``field``) and, when *step_namespace* and
    ``step_def.id`` are set, as a namespaced key (``{ns}.{id}.{field}``).
    """
    if step_result.output is None:
        return

    returns = getattr(step_def, "returns", None) or {}
    if not returns:
        return

    from tractusx_testlab.steps._checks.extraction import declared_names
    from tractusx_testlab.steps.base import StepOutput
    raw = step_result.output
    full_output: Any = StepOutput(value=raw, request=step_result.request, response=step_result.response) if not isinstance(raw, StepOutput) else raw

    # A `returns:` name is only readable when the step declared it, so a typo
    # or a guess at the step's internals fails here rather than as a `None`
    # several steps later.
    step_cls = StepRegistry.get(step_def.uses, "")
    declared = declared_names(step_cls) if step_cls is not None else None

    step_id = getattr(step_def, "id", None)
    for var_name in returns:
        value = AssertionEngine.extract_path(full_output, var_name, declared)
        context.set_variable(var_name, value)
        if step_id and step_namespace:
            context.set_variable(f"{step_namespace}.{step_id}.{var_name}", value)


async def run_script(
    script: TestScript,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager,
) -> ScriptResult:
    """Execute all steps in a script sequentially (setup → main → teardown)."""
    seed_script_defaults(script, context)
    register_script_services(script, context)

    script_start = datetime.now(UTC)

    step_results: list[StepResult] = []
    setup_results, setup_status = await execute_setup_steps(
        script, context, job_id, monitor, jobs,
    )
    if setup_status == ScriptStatus.FAILED:
        script_status = ScriptStatus.FAILED
    else:
        step_results, script_status = await execute_main_steps(
            script, context, job_id, monitor, jobs,
        )

    teardown_results = await execute_teardown_steps(
        script, context, job_id, monitor,
    )

    script_end = datetime.now(UTC)
    all_step_results = setup_results + step_results + teardown_results

    return ScriptResult(
        script_name=script.name,
        dataspace_version=script.dataspace_version,
        status=script_status,
        execution=all_step_results,
        started_at=script_start,
        finished_at=script_end,
        total_duration_s=(script_end - script_start).total_seconds(),
        assertion_summary=AssertionEngine.build_summary(all_step_results),
    )

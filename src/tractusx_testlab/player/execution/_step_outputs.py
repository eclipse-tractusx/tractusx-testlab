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


"""Publishing what a step returned into the variables a test can read.

A step's outputs are addressable only where the test said so: a ``returns:``
block names them, and a name it did not declare is a typo rather than a
``None`` three steps later. That check, and the two shapes a name is stored
under — flat, and namespaced by phase and step id — are this module's whole job,
for a top-level step and for one nested in a flow step alike.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.assertions import AssertionEngine


def store_step_outputs(
    step_def: Any,
    step_result: StepResult,
    context: StepContext,
    *,
    step_namespace: str | None = None,
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
    from tractusx_testlab.steps.step_contract import StepOutput

    raw = step_result.output
    full_output: Any = (
        StepOutput(value=raw, request=step_result.request, response=step_result.response)
        if not isinstance(raw, StepOutput)
        else raw
    )

    # A `returns:` name is only readable when the step declared it, so a typo
    # or a guess at the step's internals fails here rather than as a `None`
    # several steps later.
    step_cls = StepRegistry.get_any(step_def.uses)
    declared = declared_names(step_cls) if step_cls is not None else None

    step_id = getattr(step_def, "id", None)
    for var_name in returns:
        value = AssertionEngine.extract_path(full_output, var_name, declared)
        context.set_variable(var_name, value)
        if step_id and step_namespace:
            context.set_variable(f"{step_namespace}.{step_id}.{var_name}", value)


async def run_and_publish(
    step_cls: type,
    step_def: Any,
    step_name: str,
    context: StepContext,
    params: dict[str, Any] | None = None,
) -> StepResult:
    """Run one step and publish its ``returns:`` under the phase *context* is bound to.

    How a phase runs a step: the phase runner calls it for a top-level step, and
    the step runner binds it as the invoker a flow step runs its nested steps
    with (``StepContext.invoke_step``). The namespaced name used to be written
    by the phase runner alone, so a step inside ``flow/retry`` published nothing
    under its id and the step after it could not read
    ``${{ execution.<id>.<field> }}`` — the EDR a negotiation returned, for the
    data-plane call retried with it. A retried or looped step leaves the value
    of its latest run.
    """
    # Imported here: the step runner binds this function, so it imports this module.
    from tractusx_testlab.player.execution.step_runner import run_step

    step_result = await run_step(step_cls, step_def, step_name, context, params)
    if context.step_namespace is not None:
        store_step_outputs(step_def, step_result, context, step_namespace=context.step_namespace)
    return step_result

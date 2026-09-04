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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Holding a step to the time its script allows it.

``timeout_s`` reached the runtime definition and the compiled IR, and nothing
applied it. A step that never returned — a contract negotiation against a
connector that accepts the connection and then answers nothing — therefore ran
until CI killed the whole job: no verdict about the SUT, no teardown, and no
report on the tests that would have run after it. A bound the TCK declares and
the engine ignores is worse than no bound at all, because the TCK says the run
is bounded.

This is the author's bound, over a whole step. The bound that always applies,
declared or not, is the one on each individual SDK call
(:mod:`tractusx_testlab.steps.sdk_call`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tractusx_testlab.models import StepExecutionError

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


async def invoke_within_deadline(
    step_instance: Any,
    step_def: Any,
    params: dict[str, Any],
    context: StepContext,
) -> Any:
    """Invoke the step, failing it once its declared ``timeout_s`` has passed.

    A step that did not declare one is invoked directly rather than through a
    guard that would never fire.

    Raises:
        StepExecutionError: if the step is still running at the deadline.
    """
    if not step_def.timeout_s:
        return await step_instance.invoke(params, context, step_def)
    try:
        return await asyncio.wait_for(
            step_instance.invoke(params, context, step_def), step_def.timeout_s
        )
    except TimeoutError as exc:
        raise StepExecutionError(
            step_def.uses,
            f"did not finish within the {step_def.timeout_s:g}s the script allows it",
        ) from exc

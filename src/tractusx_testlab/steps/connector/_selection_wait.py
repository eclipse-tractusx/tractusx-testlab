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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Waiting for the operator's choice — the clock stops while the run is on hold.

The step asks (``SelectionBoard.ask``) and blocks until the answer comes, the
timeout runs out, or the question is withdrawn because the run was cancelled.
A pause stops the clock as it does for ``mock/wait`` (``_paused_wait``): the
run is held, and once it resumes the question is announced again with the time
that was left. An answer given while the run is held is kept, and taken as soon
as the run goes on.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from tractusx_testlab.models import StepExecutionError
from tractusx_testlab.models.runtime.selection import AssetSelection, SelectionOption
from tractusx_testlab.steps.dsp_keys import ASSET_ID_KEYS, POLICY_KEYS, first_present

if TYPE_CHECKING:
    from tractusx_testlab.models import StepDefinition
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

#: What a dataset carries that is not a property of the asset: its node, its
#: offers and where to fetch it from.
_NOT_PROPERTIES: frozenset[str] = frozenset(
    {"@id", "@type", "@context", *POLICY_KEYS, "distribution", "dcat:distribution"}
)


def asset_id_of(dataset: dict) -> str | None:
    """The id of the asset behind *dataset*, whichever DSP generation wrote it."""
    value = first_present(dataset, ASSET_ID_KEYS)
    return str(value) if value is not None else None


def option_of(dataset: dict) -> SelectionOption:
    """*dataset* as the operator is shown it: its id, its properties, its offers."""
    policies = first_present(dataset, POLICY_KEYS)
    if isinstance(policies, dict):
        policies = [policies]
    return SelectionOption(
        asset_id=asset_id_of(dataset) or "",
        properties={key: value for key, value in dataset.items() if key not in _NOT_PROPERTIES},
        policies=list(policies or []),
    )


async def await_choice(
    context: StepContext,
    definition: StepDefinition,
    selection: AssetSelection,
    timeout: float,
) -> tuple[str, float]:
    """The asset id the operator chose, and the seconds the step waited for it.

    Raises ``StepExecutionError`` when nobody can be asked (a context the player
    did not bind), when the timeout runs out, and when the run is cancelled.
    """
    step_type = definition.uses
    jobs = context.hold.jobs
    if jobs is None:
        raise StepExecutionError(
            step_type,
            "there is no operator to choose an asset: the step ran outside a player "
            "job. Name the asset with 'asset_id' instead.",
        )
    job_id = context.job.job_id
    answer = jobs.selections.ask(
        job_id, definition.id, [option.asset_id for option in selection.options]
    )
    try:
        waited = 0.0
        context.report_selecting(step_type, definition.id, selection, timeout)
        while True:
            started = time.monotonic()
            paused = await _answered_or_paused(context, answer, timeout - waited)
            waited += time.monotonic() - started
            if answer.done():
                break
            if not paused:
                raise StepExecutionError(
                    step_type,
                    f"no asset was chosen within {timeout:.0f}s. Offered: "
                    f"{', '.join(option.asset_id for option in selection.options)}.",
                )
            remaining = round(max(timeout - waited, 0.0), 3)
            logger.info("Paused with %.0fs left to choose an asset", remaining)
            await context.hold.pause_point()
            if not answer.done():
                context.report_selecting(step_type, definition.id, selection, remaining)
    finally:
        jobs.selections.close(job_id)
    if answer.cancelled():
        raise StepExecutionError(step_type, "the run was cancelled before an asset was chosen.")
    asset_id = answer.result()
    context.report_selected(step_type, definition.id, asset_id, round(waited * 1000))
    return asset_id, waited


async def _answered_or_paused(context: StepContext, answer: Any, timeout: float) -> bool:
    """Wait until *answer* is done, a pause is asked for, or *timeout* runs out.

    Returns whether it was the pause. ``is not True`` rather than ``not``, so a
    context double's stand-in for the hold reads as unbound.
    """
    hold = context.hold
    waits: set[asyncio.Future] = {answer}
    paused: asyncio.Future | None = None
    if hold.bound is True:
        paused = asyncio.ensure_future(hold.until_pause_requested())
        waits.add(paused)
    try:
        await asyncio.wait(waits, timeout=max(timeout, 0.0), return_when=asyncio.FIRST_COMPLETED)
    finally:
        if paused is not None and not paused.done():
            paused.cancel()
    return paused is not None and paused.done() and not paused.cancelled()

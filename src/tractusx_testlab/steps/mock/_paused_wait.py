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

"""Waiting for a callback across pauses — the clock stops while the run is on hold.

``mock/wait`` blocks on a listener with a timeout. A paused run is held
(``player.execution.hold``), and a wait that went on counting through the hold
would time out on a system under test that could not have called: the run's
offers are withdrawn and its mocks turned away while it is held. So the wait
races the pause: when the pause comes first, the listener closes, what is left
of the timeout is reported, and once the hold ends the listener opens again for
the time that was left.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tractusx_testlab.models import Listener, StepDefinition
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


async def wait_through_pauses(
    manager: Any,
    context: StepContext,
    definition: StepDefinition,
    listener: Listener,
    timeout: float,
) -> tuple[Any, float]:
    """Wait for the call, stopping the clock while the run is on hold.

    Returns the callback result and the seconds spent waiting — the stretches
    before and after each pause, not the pause itself.
    """
    path, method = listener.path, listener.method
    waited = 0.0
    while True:
        started = time.monotonic()
        result = await _wait_unless_paused(manager, path, method, timeout - waited, context)
        waited += time.monotonic() - started
        if result is not None:
            return result, waited
        # Rounded once, so the time reported as left is the time waited for.
        remaining = round(max(timeout - waited, 0.0), 3)
        context.report_suspended(
            definition.uses, definition.id, listener, remaining, round(waited * 1000)
        )
        logger.info("Paused with %.0fs left of the wait for %s %s", remaining, method, path)
        await context.hold.pause_point()
        manager.register(path, method)
        context.report_waiting(definition.uses, definition.id, listener, remaining)
        logger.info("Resumed: waiting up to %.0fs more for %s %s", remaining, method, path)


async def _wait_unless_paused(
    manager: Any, path: str, method: str, timeout: float, context: StepContext
) -> Any | None:
    """The callback result, or ``None`` when the run was paused before it came.

    A call that arrives in the same moment as the pause wins: it is the answer
    the wait was for, and a pause has nothing to hold it for. The wait that
    loses is cancelled, which closes its listener.
    """
    hold = context.hold
    wait = asyncio.ensure_future(manager.wait(path, method, max(timeout, 0.0)))
    # ``is not True`` rather than ``not``, so a context double's stand-in for
    # the hold reads as unbound instead of as a pause to race.
    if hold.bound is not True:
        return await wait
    paused = asyncio.ensure_future(hold.until_pause_requested())
    try:
        await asyncio.wait({wait, paused}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        paused.cancel()
        if not wait.done():
            wait.cancel()
    await asyncio.wait({wait})
    return None if wait.cancelled() else wait.result()

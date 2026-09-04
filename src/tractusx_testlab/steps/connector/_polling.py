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
## It was reviewed and tested by a human committer.

"""Waiting for a connector state machine to settle.

A contract negotiation and a transfer process are both stateful entities of the
connector's management API: the request that starts one answers immediately with
an ID, and the state that matters — agreed, started, terminated — arrives later.
Both step families therefore do the same thing, and they do it through the one
loop here rather than each writing its own.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

# The waiting defaults are declared once in ``steps._contracts`` and re-exported
# here, so the connector steps keep importing them from the module they poll
# with and no two steps can drift into different waits.
from tractusx_testlab.models import StepExecutionError
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.shared_models import DEFAULT_MAX_WAIT, DEFAULT_POLL_INTERVAL

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_MAX_WAIT",
    "DEFAULT_POLL_INTERVAL",
    "NEGOTIATION_TERMINAL",
    "TRANSFER_TERMINAL",
    "poll_until_terminal",
    "read_entity",
]

#: Contract-negotiation states no further polling can change.
NEGOTIATION_TERMINAL = frozenset({"FINALIZED", "TERMINATED"})

#: Transfer-process states no further polling can change.
#: ``STARTED`` is terminal for a PULL transfer — the EDR exists from then on —
#: and ``COMPLETED`` is what a PUSH transfer settles at.
TRANSFER_TERMINAL = frozenset({"STARTED", "COMPLETED", "TERMINATED", "SUSPENDED"})


async def read_entity(controller: Any, oid: str, verify: Any = None) -> dict | None:
    """Read one management-API entity by ID, or ``None`` when it cannot be read.

    An unreachable connector is reported as "no entity" rather than raised: the
    caller still has the ID it started from, and the step's own response status
    is how a script asserts on the failure.

    The read goes through :mod:`~tractusx_testlab.steps.sdk_call` like every
    other call into the SDK. It used to be made inline, which put a blocking
    ``requests`` call with no timeout on the event loop: a connector that
    accepted the connection and then answered nothing froze the loop, and with
    it every timer the run relies on — including the deadline meant to stop
    exactly that. The loop cannot enforce a bound it is not running.
    """
    if not oid:
        return None
    # Left out entirely when unset so the SDK adapter keeps its own default.
    options = {} if verify is None else {"verify": verify}
    try:
        response = await sdk_call.run(controller.get_by_id, oid=oid, **options)
    except StepExecutionError:
        raise
    except Exception as exc:
        logger.debug("Could not read entity %s: %s", oid, exc)
        return None
    if response is None or getattr(response, "status_code", 0) != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


async def poll_until_terminal(
    controller: Any,
    oid: str,
    terminal_states: frozenset[str],
    max_wait: float = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: Any = None,
    *,
    what: str = "connector/poll",
    allow_timeout: bool = False,
) -> dict:
    """Read *oid* until its ``state`` is in *terminal_states* or *max_wait* elapses.

    Returns the entity once its state is terminal.

    A timeout is a failure, not a result. It used to return whatever state had
    last been observed and log a warning, so a negotiation that never reached
    FINALIZED and one that reached it in 200 ms produced the same shape and the
    step passed either way unless the TCK happened to assert on ``state``. A
    conformance run cannot report on a state machine that never settled.

    *allow_timeout* is the escape hatch for the case where not settling is the
    thing under test — it has to be asked for, in the script, in writing.

    The connector answers a create request only once the entity is persisted, so
    a first read that fails means the entity cannot be observed at all — polling
    stops there rather than spending *max_wait* on a connector that will not
    answer.

    Raises:
        StepExecutionError: if the entity never settles, or cannot be read.
    """
    if not oid:
        raise StepExecutionError(what, "no id to watch — the create call returned none")
    if not callable(getattr(controller, "get_by_id", None)):
        raise StepExecutionError(
            what, "the connector service exposes no controller to read this from"
        )

    deadline = time.monotonic() + max_wait
    entity: dict = {}
    while True:
        current = await read_entity(controller, oid, verify)
        if current is None and not entity:
            if allow_timeout:
                return {}
            raise StepExecutionError(what, f"{oid} cannot be read from the connector")
        entity = current or entity
        if str(entity.get("state", "")) in terminal_states:
            return entity
        if time.monotonic() + poll_interval > deadline:
            if allow_timeout:
                logger.warning(
                    "Entity %s did not settle within %ss (state=%r); allowed by the step",
                    oid,
                    max_wait,
                    entity.get("state"),
                )
                return entity
            raise StepExecutionError(
                what,
                f"{oid} did not reach a final state within {max_wait}s — last seen "
                f"{entity.get('state')!r}, waiting for one of "
                f"{', '.join(sorted(terminal_states))}",
            )
        await asyncio.sleep(poll_interval)

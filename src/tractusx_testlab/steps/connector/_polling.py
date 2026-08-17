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
# License for the specific language govern in permissions and limitations
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
from tractusx_testlab.steps._contracts import DEFAULT_MAX_WAIT, DEFAULT_POLL_INTERVAL

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


def read_entity(controller: Any, oid: str, verify: Any = None) -> dict | None:
    """Read one management-API entity by ID, or ``None`` when it cannot be read.

    An unreachable connector is reported as "no entity" rather than raised: the
    caller still has the ID it started from, and the step's own response status
    is how a script asserts on the failure.
    """
    if not oid:
        return None
    # Left out entirely when unset so the SDK adapter keeps its own default.
    options = {} if verify is None else {"verify": verify}
    try:
        response = controller.get_by_id(oid=oid, **options)
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
) -> dict:
    """Read *oid* until its ``state`` is in *terminal_states* or *max_wait* elapses.

    Returns the last entity that could be read — empty when none ever could.
    Neither timing out nor an unreadable entity is an error here: whatever state
    was observed is the answer, and the step publishes it so the script can
    assert on it.

    The connector answers a create request only once the entity is persisted, so
    a first read that fails means the entity cannot be observed at all — polling
    stops there rather than spending *max_wait* on a connector that will not
    answer.
    """
    if not oid or not callable(getattr(controller, "get_by_id", None)):
        # No entity to watch, or a service that does not expose this controller.
        return {}

    deadline = time.monotonic() + max_wait
    entity: dict = {}
    while True:
        current = read_entity(controller, oid, verify)
        if current is None and not entity:
            logger.warning("Entity %s cannot be read; reporting no state", oid)
            return {}
        entity = current or entity
        if str(entity.get("state", "")) in terminal_states:
            return entity
        if time.monotonic() + poll_interval > deadline:
            logger.warning(
                "Entity %s did not settle within %ss (state=%r)",
                oid, max_wait, entity.get("state"),
            )
            return entity
        await asyncio.sleep(poll_interval)

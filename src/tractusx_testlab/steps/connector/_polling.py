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

The EDR a PULL transfer produces is the same kind of wait one step removed:
the negotiation's own transfer writes it, so :func:`await_edr_entry` polls for
the entry and reads that transfer for the reason while it is missing.
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
    "await_edr_entry",
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
    is how a test asserts on the failure.
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
    thing under test — it has to be asked for, in the test, in writing.

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
        current = read_entity(controller, oid, verify)
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


async def await_edr_entry(
    consumer: Any,
    negotiation_id: str,
    *,
    max_wait: float = DEFAULT_MAX_WAIT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    verify: Any = None,
    what: str = "connector/poll",
) -> dict:
    """Wait for the EDR the negotiation's transfer writes, and return it.

    A FINALIZED negotiation is not yet an EDR. The EDR API starts a transfer
    process the moment the negotiation finalises, and the EDR is written only
    when that transfer reaches STARTED — a second or so later on a healthy
    connector. The step that waited for the negotiation therefore hands over
    an id whose EDR does not exist yet, and a single query here answered an
    empty list.

    While the EDR is missing the transfer process is what says why: it exists
    before the EDR does, and it carries the ``errorDetail`` when the provider
    turned the transfer down. It is read by the agreement id the negotiation
    settled on, so a terminated transfer fails the step at once instead of at
    the end of *max_wait*.

    Raises:
        StepExecutionError: if the transfer terminated, or the EDR never appeared.
    """
    deadline = time.monotonic() + max_wait
    agreement_id: str | None = None
    transfer: dict = {}
    while True:
        edr_entry = await sdk_call.run(
            consumer.get_edr_entry, negotiation_id=negotiation_id, verify=verify
        )
        if edr_entry:
            return edr_entry

        agreement_id = agreement_id or _agreement_id_of(consumer, negotiation_id, verify)
        if agreement_id:
            transfer = await _transfer_for(consumer, agreement_id, verify) or transfer
        state = str(transfer.get("state", ""))
        if state == "TERMINATED":
            raise StepExecutionError(
                what,
                f"the transfer the negotiation {negotiation_id} started was terminated "
                f"before it produced an EDR: {transfer.get('errorDetail') or 'no detail given'}",
            )

        if time.monotonic() + poll_interval > deadline:
            seen = f"transfer last seen {state!r}" if state else "no transfer process observed"
            raise StepExecutionError(
                what,
                f"the negotiation {negotiation_id} produced no EDR within "
                f"{max_wait}s ({seen}), so this PULL transfer has no "
                "data-plane address or token to hand on.",
            )
        await asyncio.sleep(poll_interval)


def _agreement_id_of(consumer: Any, negotiation_id: str, verify: Any) -> str | None:
    """The agreement id a finalised negotiation carries, or ``None`` if unreadable."""
    negotiation = read_entity(
        getattr(consumer, "contract_negotiations", None), negotiation_id, verify
    )
    return (negotiation or {}).get("contractAgreementId") or None


async def _transfer_for(consumer: Any, agreement_id: str, verify: Any) -> dict | None:
    """The transfer process running under *agreement_id*, or ``None`` if none yet."""
    try:
        transfer = await sdk_call.run(
            consumer.get_transfer_process, agreement_id=agreement_id, verify=verify
        )
    except Exception as exc:  # The EDR query decides; this read only explains.
        logger.debug("Could not read the transfer for agreement %s: %s", agreement_id, exc)
        return None
    return transfer if isinstance(transfer, dict) else None

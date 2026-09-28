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

"""A paused run on hold: its offers withdrawn until it resumes.

Pausing used to close a gate the run checked between steps, and nothing more.
Whatever the run had published stayed published: the system under test could
still find its offers in the catalog, negotiate them and call through, and a
step waiting for that call went on counting down its timeout. The run was
paused; what it had opened to the outside was not.

On hold, the run stops as though it had been cancelled. Every contract
definition the run created is withdrawn from the connector — its assets and
policies stay, but nothing offers them — and the host is told the run is held
(``JobManager.is_held``), so it can answer the run's mocks as it answers those
of a run that is not going. A wait for a callback stops with its timeout where
it was (``mock/wait``). On resume the definitions are created again, as they
were, the host is told, and the wait carries on for the time it had left.

Only what the run created is withdrawn. A contract definition that was already
on the connector (the create answered 409) belongs to whoever made it, and one
the run deleted itself is no longer anyone's to put back.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.monitor import ExecutionMonitor
    from tractusx_testlab.player.jobs import JobManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Offer:
    """A contract definition the run created, and how to take it down and put it back."""

    definition_id: str
    withdraw: Callable[[], Any]
    restore: Callable[[], Any]


class RunHold:
    """What one run withdraws while it is paused, and puts back when it resumes.

    Built unbound — the offers are recorded, a pause point is a no-op — for a
    context made outside the player; the player binds it to the job before the
    first step (:meth:`bind`).
    """

    __slots__ = ("_job_id", "_jobs", "_monitor", "_offers")

    def __init__(self) -> None:
        self._jobs: JobManager | None = None
        self._job_id = ""
        self._monitor: ExecutionMonitor | None = None
        self._offers: dict[str, _Offer] = {}

    def bind(self, jobs: JobManager, job_id: str, monitor: ExecutionMonitor) -> None:
        """Tie the hold to the job it pauses, and to the monitor that reports it."""
        self._jobs = jobs
        self._job_id = job_id
        self._monitor = monitor

    @property
    def bound(self) -> bool:
        """Whether the hold belongs to a job the player runs."""
        return self._jobs is not None

    # ------------------------------------------------------------------
    # What the run has published
    # ------------------------------------------------------------------

    def offer(
        self, definition_id: str, *, withdraw: Callable[[], Any], restore: Callable[[], Any]
    ) -> None:
        """Record a contract definition the run created, with the calls that undo and redo it."""
        self._offers[definition_id] = _Offer(definition_id, withdraw, restore)

    def forget(self, definition_id: str) -> None:
        """Stop tracking a contract definition the run has deleted itself."""
        self._offers.pop(definition_id, None)

    @property
    def offers(self) -> list[str]:
        """The contract definitions a hold would withdraw, in the order they were created."""
        return list(self._offers)

    # ------------------------------------------------------------------
    # Pausing
    # ------------------------------------------------------------------

    @property
    def pause_requested(self) -> bool:
        """Whether the run has been asked to pause and has not been let go yet."""
        if self._jobs is None:
            return False
        return not self._jobs.get_pause_event(self._job_id).is_set()

    async def until_pause_requested(self) -> None:
        """Return once the run is asked to pause; never, for an unbound hold."""
        if self._jobs is None:
            # Nothing can pause a run the player does not hold: wait forever,
            # so a race against this is decided by the other side.
            await asyncio.get_running_loop().create_future()
            return
        request = self._jobs.get_pause_request(self._job_id)
        while True:
            await request.wait()
            if self.pause_requested:
                return
            # The gate was opened without a resume — a paused run cancelled
            # before it got to hold — so the request is stale.
            request.clear()

    async def gate(self, jobs: JobManager, job_id: str) -> None:
        """The pause gate between two steps: held here (:meth:`pause_point`) while paused.

        A context the player did not bind has no hold, and only waits on *jobs*' gate.
        """
        if self.bound:
            await self.pause_point()
        else:
            await jobs.get_pause_event(job_id).wait()

    async def pause_point(self) -> bool:
        """Hold the run here if it is asked to pause; returns whether it was held.

        Withdraws the run's offers and tells the host, waits for the gate to
        open, then puts the offers back. The gate opens on resume, and also
        when a paused run is cancelled — the offers are put back then too, so
        the teardown finds and deletes what it created, as it would have had
        the run never been paused.
        """
        if self._jobs is None:
            return False
        jobs, job_id = self._jobs, self._job_id
        if not self.pause_requested:
            jobs.get_pause_request(job_id).clear()
            return False
        jobs.hold(job_id, True)
        withdrawn: list[str] = []
        try:
            withdrawn, kept = self._withdraw()
            if self._monitor is not None:
                self._monitor.on_job_held(job_id, withdrawn, kept)
            await jobs.get_pause_event(job_id).wait()
            # A cancelled pause opens the gate without resuming the job, which
            # leaves the request standing: cleared here so the next wait does
            # not stop on it again.
            jobs.get_pause_request(job_id).clear()
        finally:
            # Whatever ends the hold — a resume, or a cancellation raised out
            # of the event above — the definitions go back before the run goes
            # on, so its teardown finds what it created.
            restored, lost = self._restore(withdrawn)
            jobs.hold(job_id, False)
        if self._monitor is not None:
            self._monitor.on_job_restored(job_id, restored, lost)
        return True

    def _withdraw(self) -> tuple[list[str], dict[str, str]]:
        """Delete the run's contract definitions, last created first.

        One the connector refuses to delete is reported, not raised: the rest
        are still withdrawn, and the run still pauses.
        """
        withdrawn: list[str] = []
        kept: dict[str, str] = {}
        for offer in reversed(self._offers.values()):
            try:
                offer.withdraw()
            except Exception as exc:  # reported; the hold goes on
                logger.warning("Could not withdraw %s for the pause: %s", offer.definition_id, exc)
                kept[offer.definition_id] = str(exc) or type(exc).__name__
            else:
                withdrawn.append(offer.definition_id)
        withdrawn.reverse()
        return withdrawn, kept

    def _restore(self, withdrawn: list[str]) -> tuple[list[str], dict[str, str]]:
        """Create again, in the order they were first created, the definitions the hold withdrew."""
        restored: list[str] = []
        lost: dict[str, str] = {}
        for definition_id in withdrawn:
            offer = self._offers.get(definition_id)
            if offer is None:
                continue
            try:
                offer.restore()
            except Exception as exc:  # reported; the run goes on
                logger.warning("Could not restore %s after the pause: %s", definition_id, exc)
                lost[definition_id] = str(exc) or type(exc).__name__
            else:
                restored.append(definition_id)
        return restored, lost

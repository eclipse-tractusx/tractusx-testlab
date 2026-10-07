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

"""A paused run on hold: its contract definitions withdrawn, and put back on resume."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.player.execution.hold import RunHold
from tractusx_testlab.player.jobs import JobManager


def _running() -> tuple[JobManager, str]:
    jobs = JobManager()
    job = jobs.create("tck")
    jobs.start(job.job_id)
    return jobs, job.job_id


def _bound(calls: list[str]) -> tuple[RunHold, JobManager, str, MagicMock]:
    jobs, job_id = _running()
    monitor = MagicMock()
    hold = RunHold()
    hold.bind(jobs, job_id, monitor)
    for definition_id in ("cd-1", "cd-2"):
        hold.offer(
            definition_id,
            withdraw=lambda d=definition_id: calls.append(f"delete {d}"),
            restore=lambda d=definition_id: calls.append(f"create {d}"),
        )
    return hold, jobs, job_id, monitor


class _Cancelled(Exception):
    """What a host raises from a monitor callback to stop a cancelled run."""


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


class TestAnUnpausedRun:
    @pytest.mark.asyncio
    async def test_a_pause_point_lets_it_through_and_withdraws_nothing(self) -> None:
        calls: list[str] = []
        hold, _, _, monitor = _bound(calls)

        assert await hold.pause_point() is False
        assert calls == []
        monitor.on_job_held.assert_not_called()

    @pytest.mark.asyncio
    async def test_an_unbound_hold_records_but_never_holds(self) -> None:
        hold = RunHold()
        hold.offer("cd-1", withdraw=MagicMock(), restore=MagicMock())

        assert hold.offers == ["cd-1"]
        assert hold.pause_requested is False
        assert await hold.pause_point() is False

    @pytest.mark.asyncio
    async def test_an_unbound_hold_waits_on_the_gate_it_is_given(self) -> None:
        jobs, job_id = _running()
        jobs.pause(job_id)
        gate = asyncio.ensure_future(RunHold().gate(jobs, job_id))
        await _settle()
        assert not gate.done()

        jobs.resume(job_id)
        await asyncio.wait_for(gate, 1)


class TestAPausedRun:
    @pytest.mark.asyncio
    async def test_it_withdraws_its_definitions_last_first_and_restores_them_in_order(
        self,
    ) -> None:
        calls: list[str] = []
        hold, jobs, job_id, _ = _bound(calls)
        jobs.pause(job_id)

        held = asyncio.ensure_future(hold.pause_point())
        await _settle()
        assert calls == ["delete cd-2", "delete cd-1"]
        assert not held.done()

        jobs.resume(job_id)
        assert await asyncio.wait_for(held, 1) is True
        assert calls[2:] == ["create cd-1", "create cd-2"]

    @pytest.mark.asyncio
    async def test_the_job_reads_held_only_while_it_is(self) -> None:
        hold, jobs, job_id, _ = _bound([])
        jobs.pause(job_id)
        assert jobs.is_held(job_id) is False  # asked, not yet stopped

        held = asyncio.ensure_future(hold.pause_point())
        await _settle()
        assert jobs.is_held(job_id) is True
        assert jobs.any_held() is True

        jobs.resume(job_id)
        await asyncio.wait_for(held, 1)
        assert jobs.is_held(job_id) is False

    @pytest.mark.asyncio
    async def test_it_reports_what_it_withdrew_and_what_it_put_back(self) -> None:
        hold, jobs, job_id, monitor = _bound([])
        jobs.pause(job_id)
        held = asyncio.ensure_future(hold.pause_point())
        await _settle()
        monitor.on_job_held.assert_called_once_with(job_id, ["cd-1", "cd-2"], {})

        jobs.resume(job_id)
        await asyncio.wait_for(held, 1)
        monitor.on_job_restored.assert_called_once_with(job_id, ["cd-1", "cd-2"], {})

    @pytest.mark.asyncio
    async def test_a_definition_the_connector_keeps_is_reported_and_not_recreated(
        self,
    ) -> None:
        calls: list[str] = []
        hold, jobs, job_id, monitor = _bound(calls)

        def _refuse() -> None:
            raise ValueError("409 referenced")

        hold.offer("cd-3", withdraw=_refuse, restore=lambda: calls.append("create cd-3"))
        jobs.pause(job_id)
        held = asyncio.ensure_future(hold.pause_point())
        await _settle()
        jobs.resume(job_id)
        await asyncio.wait_for(held, 1)

        monitor.on_job_held.assert_called_once_with(
            job_id, ["cd-1", "cd-2"], {"cd-3": "409 referenced"}
        )
        assert "create cd-3" not in calls

    @pytest.mark.asyncio
    async def test_a_definition_the_run_deleted_is_left_alone(self) -> None:
        calls: list[str] = []
        hold, jobs, job_id, _ = _bound(calls)
        hold.forget("cd-1")
        jobs.pause(job_id)
        held = asyncio.ensure_future(hold.pause_point())
        await _settle()
        jobs.resume(job_id)
        await asyncio.wait_for(held, 1)

        assert calls == ["delete cd-2", "create cd-2"]


class TestACancelledPause:
    @pytest.mark.asyncio
    async def test_the_definitions_are_put_back_for_the_teardown(self) -> None:
        calls: list[str] = []
        hold, jobs, job_id, _ = _bound(calls)
        jobs.pause(job_id)
        held = asyncio.ensure_future(hold.pause_point())
        await _settle()

        # What the engine does to cancel a paused run: open the gate, no resume.
        jobs.get_pause_event(job_id).set()
        await asyncio.wait_for(held, 1)

        assert calls == ["delete cd-2", "delete cd-1", "create cd-1", "create cd-2"]
        assert jobs.is_held(job_id) is False

    @pytest.mark.asyncio
    async def test_the_request_it_leaves_behind_does_not_stop_the_next_wait(self) -> None:
        hold, jobs, job_id, _ = _bound([])
        jobs.pause(job_id)
        jobs.get_pause_event(job_id).set()  # cancelled before the run got to hold

        waiting = asyncio.ensure_future(hold.until_pause_requested())
        await _settle()
        assert not waiting.done()
        waiting.cancel()
        assert await hold.pause_point() is False

    @pytest.mark.asyncio
    async def test_a_cancellation_raised_while_holding_still_puts_them_back(self) -> None:
        calls: list[str] = []
        hold, jobs, job_id, monitor = _bound(calls)
        monitor.on_job_held.side_effect = _Cancelled
        jobs.pause(job_id)

        with pytest.raises(_Cancelled):
            await hold.pause_point()

        assert calls == ["delete cd-2", "delete cd-1", "create cd-1", "create cd-2"]
        assert jobs.is_held(job_id) is False

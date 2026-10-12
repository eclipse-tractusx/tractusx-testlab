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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The monitor's inbound and selection events, as the checkpoints follow them (ADR-0028).

A real monitor, a real trace and a real tracker, driven in the order the steps
drive them: what a host and the trace receive, and what the checkpoint becomes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from tractusx_testlab.authoring._checkpoints import PlannedCheckpoint
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models.primitives.checkpoint import Direction
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry
from tractusx_testlab.models.runtime.events import Listener
from tractusx_testlab.models.runtime.listener import InboundAnswer
from tractusx_testlab.models.runtime.results import CallbackResult
from tractusx_testlab.models.runtime.selection import Selection, SelectionOption
from tractusx_testlab.player.checkpoints import CheckpointTracker
from tractusx_testlab.player.execution.monitor import ExecutionMonitor

_LISTENER = Listener(method="POST", url="http://mock/cb", path="/cb")
_WAIT = CheckpointEntry(
    test_id="t",
    test_name="t",
    phase="execution",
    position="execution/0",
    step_id="wait",
    uses="mock/wait/http_request",
    direction=Direction.INBOUND,
    kind="wait",
)


class _Host:
    """Everything a host receives: the events, and their envelopes."""

    def __init__(self, monitor: ExecutionMonitor) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.envelopes: list[dict[str, Any] | None] = []
        monitor.add_callback(lambda event, payload: self.events.append((event, payload)))
        monitor.add_trace_callback(lambda _e, _p, envelope: self.envelopes.append(envelope))

    def of(self, name: str) -> list[dict[str, Any]]:
        return [payload for event, payload in self.events if event == name]

    def states(self) -> list[str]:
        return [u["checkpoint"]["state"] for u in self.of("checkpoint.updated")]


def _followed(tmp_path: Path, *planned: PlannedCheckpoint):
    trace = ExecutionTrace("tck", tmp_path / "trace.jsonl")
    monitor = ExecutionMonitor(MagicMock(), trace)
    host = _Host(monitor)
    tracker = CheckpointTracker(list(planned), monitor.checkpoint_publisher("job"))
    monitor.follow_checkpoints(tracker)
    return monitor, tracker, host, trace


def _received(monitor: ExecutionMonitor, request: CallbackResult) -> None:
    monitor.on_step_received(
        "job", "t", "wait", "mock/wait/http_request", "execution", _LISTENER, request, 1500
    )


def test_a_call_turned_away_never_reads_as_cleared(tmp_path: Path) -> None:
    monitor, tracker, host, _ = _followed(
        tmp_path, PlannedCheckpoint(entry=_WAIT, path=("execution", 0), asks=True)
    )
    with tracker.step("t", ("execution", 0)):
        monitor.on_step_waiting(
            "job", "t", "wait", "mock/wait/http_request", "execution", _LISTENER, 10
        )
        _received(
            monitor,
            CallbackResult(
                listener_name="POST:/cb",
                path="/cb",
                refused="no key",
                response=InboundAnswer(status_code=401, body={"error": "unauthorized"}),
            ),
        )
        assert host.states() == ["now"]
        tracker.ended(StepStatus.FAILED)
    assert host.states() == ["now", "failed"]
    assert host.of("checkpoint.updated")[-1]["checkpoint"]["response_s"] is None


def test_the_answer_body_of_a_mock_is_redacted_everywhere_it_goes(tmp_path: Path) -> None:
    monitor, _, host, trace = _followed(tmp_path)
    request = CallbackResult(
        listener_name="POST:/cb",
        path="/cb",
        headers={"Authorization": "HDRSECRET"},
        response=InboundAnswer(
            status_code=200,
            body={"access_token": "MOCKTOKEN123", "authorization": "EDRSECRET", "kept": "v"},
        ),
    )
    _received(monitor, request)
    trace.close()

    written = str(host.events) + str(host.envelopes) + (tmp_path / "trace.jsonl").read_text()
    for secret in ("MOCKTOKEN123", "EDRSECRET", "HDRSECRET"):
        assert secret not in written
    (payload,) = host.of("step.received")
    assert payload["request"]["response"]["body"] == {
        "access_token": "***",
        "authorization": "***",
        "kept": "v",
    }
    (envelope,) = [e for e in host.envelopes if e and e["type"] == "tck.test.step.received"]
    assert envelope["data"]["response"]["body"]["access_token"] == "***"
    assert request.response is not None and request.response.body["access_token"] == "MOCKTOKEN123"


def test_a_choice_that_is_no_checkpoint_counts_its_pauses(tmp_path: Path) -> None:
    monitor, tracker, host, _ = _followed(tmp_path)
    selection = Selection(options=[SelectionOption(id="a", label="A")])
    with tracker.step("t", ("execution", 0)):
        for remaining in (60.0, 42.0):  # asked, then put again after a pause
            monitor.on_step_selecting(
                "job", "t", "pick", "flow/select", "execution", selection, remaining
            )
    assert [p["pauses"] for p in host.of("step.selecting")] == [0, 1]
    assert host.of("checkpoint.updated") == []

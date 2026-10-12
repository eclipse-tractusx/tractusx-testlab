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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""No two events of a run share an id — and not because the trace had to step in (ADR-0016).

The run of ``test_checkpoint_journey`` retries a wait, restarts a test, pauses a
wait twice, asks a re-asked question, answers calls and cancels a choice. Every
event that repeats at one place carries what makes it another: its
``attempt``, its ``pauses``, its ``occurrence``, its ``revision``. The trace's
own last resort — adding ``occurrence`` to data that did not tell two events
apart — is never needed for it.
"""

from __future__ import annotations

import json
from collections import Counter

from combinations.checkpoint_tck import Run
from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.player.execution.monitor import ExecutionMonitor

#: The events whose data counts its occurrences on purpose.
_COUNTED = {"tck.held", "tck.restored", "tck.test.awaiting"}


def test_every_event_of_the_run_has_an_id_of_its_own(checkpoint_run: Run) -> None:
    repeated = [
        i for i, n in Counter(event["id"] for event in checkpoint_run.trace).items() if n > 1
    ]
    assert not repeated


def test_the_trace_never_had_to_number_an_occurrence(checkpoint_run: Run) -> None:
    numbered = [
        event["type"]
        for event in checkpoint_run.trace
        if "occurrence" in event["data"] and event["type"] not in _COUNTED
    ]
    assert not numbered


def test_a_second_pause_says_it_is_the_second(checkpoint_run: Run) -> None:
    held = [e["data"]["occurrence"] for e in checkpoint_run.trace if e["type"] == "tck.held"]
    restored = [
        e["data"]["occurrence"] for e in checkpoint_run.trace if e["type"] == "tck.restored"
    ]
    assert held == restored == [1, 2]


def test_a_retried_and_a_restarted_step_say_which_attempt(checkpoint_run: Run) -> None:
    starts = [e for e in checkpoint_run.trace if e["type"] == "tck.test.step.start"]
    attempts = {e["id"].split("/")[1]: e["data"]["attempt"] for e in starts}
    assert attempts["choice"] == 2  # the latest start of the restarted test
    waits = [e for e in checkpoint_run.trace if e["type"] == "tck.test.step.waiting"]
    again = [e["data"]["attempt"] for e in waits if "/await_again/" in e["id"]]
    assert again == [1, 2]
    ended = [
        e
        for e in checkpoint_run.trace
        if e["type"].startswith("tck.test.step.") and "/pick/" in e["id"]
    ]
    assert {e["data"]["attempt"] for e in ended} == {1, 2}


def test_what_the_host_receives_never_repeats_either(checkpoint_run: Run) -> None:
    """The engine names the events it is handed by their data too."""
    seen = Counter(
        (event, json.dumps(payload, sort_keys=True, default=str))
        for event, payload in checkpoint_run.answers.events
        if not event.startswith("tck.package.")
    )
    assert not [key for key, n in seen.items() if n > 1]


def test_an_announcement_and_a_pause_repeated_by_the_host_are_numbered(tmp_path) -> None:
    trace = ExecutionTrace("demo-tck")
    monitor = ExecutionMonitor(StructuredLogger("t", logs_dir=tmp_path), trace)
    received: list[tuple[str, dict]] = []
    monitor.add_callback(lambda event, payload: received.append((event, payload)))

    for _ in range(2):
        monitor.on_test_awaiting("job", "push", 0)
        monitor.on_job_paused("job")
        monitor.on_job_resumed("job")

    occurrences = [(event, payload["occurrence"]) for event, payload in received]
    assert occurrences == [
        ("test.awaiting", 1),
        ("job.paused", 1),
        ("job.resumed", 1),
        ("test.awaiting", 2),
        ("job.paused", 2),
        ("job.resumed", 2),
    ]

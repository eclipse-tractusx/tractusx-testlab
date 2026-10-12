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

"""A TCK made of checkpoints, and a system under test and an operator that answer them.

One test per way a checkpoint can go: a wait answered, a wait nobody answers,
a choice, a ``flow/if`` branch not taken (with a step the test marks a
checkpoint in the branch taken), a ``flow/retry`` that asks twice, a wait
paused twice, a step marked in YAML beside one switched off, and a choice the
run is cancelled at. :class:`Answers` plays the system under test and the
operator from the run's own events, the way a person watching would.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml

from combinations.mock_server_double import free_port
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player import TestlabPlayer
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.server.mock_registry import (
    clear_callback_manager,
    clear_mocks,
    required_header,
)

TCK_ID = "checkpoint-tck"
TESTS = ("wait-answered", "wait-silent", "choice", "branch", "retry", "paused", "marked", "cancel")


def _mock(step_id: str, path: str) -> dict:
    return {
        "id": step_id,
        "uses": "mock/api",
        "with": {
            "path": path,
            "method": "POST",
            "response_status": 202,
            "response_body": {"ok": 1},
        },
        "returns": {"mock": {"type": "object"}},
    }


def _wait(step_id: str, mock: str, timeout_s: float, **extra: Any) -> dict:
    return {
        "id": step_id,
        "uses": "mock/wait/http_request",
        "with": {"mock": f"${{{{ execution.{mock}.mock }}}}", "timeout_s": timeout_s, **extra},
    }


def _select(step_id: str, *options: str, **extra: Any) -> dict:
    return {"id": step_id, "uses": "flow/select", "with": {"options": list(options), **extra}}


STEPS: dict[str, list[dict]] = {
    "wait-answered": [
        _mock("endpoint", "/answered"),
        _wait("await_call", "endpoint", 10, action={"label": "Push the certificate"}),
    ],
    "wait-silent": [_mock("silent", "/silent"), _wait("await_silence", "silent", 0.4)],
    "choice": [_select("pick", "alpha", "beta", timeout_s=10, action={"label": "Pick one"})],
    "branch": [
        {
            "id": "decide",
            "uses": "flow/if",
            "with": {
                "conditions": [{"input": "no", "operator": "equals", "value": "yes"}],
                "then": [_select("never", "a", "b")],
                "else": [
                    {
                        "id": "note",
                        "uses": "util/log",
                        "with": {"message": "the else branch"},
                        "checkpoint": {"label": "The else branch ran"},
                    }
                ],
            },
        }
    ],
    "retry": [
        _mock("again_mock", "/again"),
        {
            "id": "again",
            "uses": "flow/retry",
            "with": {
                "max_attempts": 2,
                "delay_s": 0,
                "steps": [_wait("await_again", "again_mock", 0.4)],
            },
        },
    ],
    "paused": [_mock("held_mock", "/held"), _wait("await_held", "held_mock", 10)],
    "marked": [
        {
            "id": "announce",
            "uses": "util/log",
            "with": {"message": "hello"},
            "checkpoint": {"label": "Announced", "description": "The run says hello"},
        },
        {**_select("only", "only"), "checkpoint": False},
    ],
    "cancel": [_select("abandoned", "x", "y", timeout_s=10)],
}


def author(root: Path) -> Path:
    """Write the TCK's sources under *root* and return its manifest."""
    (root / "tests").mkdir(parents=True)
    manifest = {
        "kind": "tck",
        "syntax": "v1-alpha",
        "id": TCK_ID,
        "metadata": {
            "name": "Checkpoint TCK",
            "version": "v1.0.0",
            "description": "Every way a checkpoint can go.",
            "authors": [{"name": "TestLab", "email": "t@example.org", "company": "Eclipse"}],
            "copyright_holders": ["2026 Contributors to the Eclipse Foundation"],
            "license": "Apache-2.0",
            "standards": [{"id": "TESTLAB-INTERNAL", "version": "v1.0.0"}],
        },
        "tests": [{"id": f"{test}.yaml", "name": test} for test in TESTS],
    }
    (root / "index.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    for test in TESTS:
        document = {
            "kind": "test",
            "syntax": "v1-alpha",
            "namespace": TCK_ID,
            "id": test,
            "metadata": {"name": test, "version": "v1.0.0", "description": test},
            "execution": STEPS[test],
        }
        (root / "tests" / f"{test}.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")
    return root / "index.yaml"


class Answers:
    """The system under test and the operator, acting on what the run publishes."""

    def __init__(self, player: TestlabPlayer, loop: asyncio.AbstractEventLoop) -> None:
        self.player = player
        self.loop = loop
        self.events: list[tuple[str, dict]] = []
        self.calls: list[threading.Thread] = []

    def __call__(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))
        handler = getattr(self, "_" + event.replace(".", "_"), None)
        if handler is not None:
            handler(payload)

    def of(self, name: str) -> list[dict]:
        return [payload for event, payload in self.events if event == name]

    def _step_waiting(self, payload: dict) -> None:
        step, jobs = payload["step_id"], self.player.jobs
        if step == "await_call" or (step == "await_again" and payload["attempt"] == 2):
            self._call(payload)
        elif step == "await_held" and payload["pauses"] < 2:
            self.loop.call_soon(jobs.pause, payload["job_id"])
        elif step == "await_held":
            self._call(payload)

    def _job_held(self, payload: dict) -> None:
        self.loop.call_soon(self.player.jobs.resume, payload["job_id"])

    def _step_selecting(self, payload: dict) -> None:
        jobs, job_id = self.player.jobs, payload["job_id"]
        if payload["step_id"] == "pick":
            self.loop.call_soon(jobs.selections.answer, job_id, "beta", "pick")
        elif payload["step_id"] == "abandoned":
            self.loop.call_soon(jobs.cancel, job_id)

    def _call(self, payload: dict) -> None:
        """POST to the address the wait announced, from another thread, as a SUT would."""
        listener = payload["listener"]
        guard = required_header(listener["path"], "POST", run=payload["job_id"])
        headers = dict([guard]) if guard else {}
        url = listener["url"].replace("localhost", "127.0.0.1")
        thread = threading.Thread(target=_post, args=(url, headers))
        thread.start()
        self.calls.append(thread)


def _post(url: str, headers: dict) -> None:
    """Call until the mock server the player started is up — it starts in the background."""
    deadline = time.monotonic() + 5
    while True:
        try:
            requests.post(url, json={"cert": 1}, headers=headers, timeout=5)
            return
        except requests.ConnectionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def compile_package(root: Path) -> Path:
    """Compile the TCK under *root* the way the CLI does; returns the package."""
    from tractusx_testlab.cli.compile import compile as compile_command

    compile_command(
        manifest=author(root / "src"),
        compiler_keys=None,
        player_pub=None,
        output=root / "dist",
        version=None,
        plain=False,
    )
    return root / "dist" / f"{TCK_ID}.tck"


class Run:
    """What one run published: to its host (the callbacks) and to its own trace."""

    def __init__(self, answers: Answers, trace: list[dict]) -> None:
        self.answers = answers
        self.trace = trace

    def planned(self) -> list[dict]:
        (event,) = self.answers.of("checkpoints.planned")
        return event["checkpoints"]

    def index(self, step_id: str) -> int:
        return next(i for i, point in enumerate(self.planned()) if point["step_id"] == step_id)

    def updates(self, step_id: str) -> list[dict]:
        index = self.index(step_id)
        return [u for u in self.answers.of("checkpoint.updated") if u["index"] == index]

    def states(self, step_id: str) -> list[str]:
        return [update["checkpoint"]["state"] for update in self.updates(step_id)]

    def final(self, step_id: str) -> dict:
        return self.updates(step_id)[-1]["checkpoint"]


def play(package: Path, tmp_path_factory: pytest.TempPathFactory) -> Run:
    """Run *package* once, answered by :class:`Answers`; ``choice`` is run twice."""
    clear_mocks()
    clear_callback_manager()
    data_dir = tmp_path_factory.mktemp("data")
    config = TestlabConfig(
        logs_dir=tmp_path_factory.mktemp("logs"), data_dir=data_dir, server_port=free_port()
    )
    player = TestlabPlayer(config=config)

    async def play() -> Answers:
        answers = Answers(player, asyncio.get_running_loop())
        player.monitor.add_callback(answers)
        session = await player.open_session(Loader().load(package))
        await session.run_scheduled()
        await session.run_test("choice")  # the same test again: a restart
        await session.close()
        for call in answers.calls:
            call.join(5)
        return answers

    try:
        answers = asyncio.run(play())
    finally:
        clear_mocks()
        clear_callback_manager()
    (trace_file,) = data_dir.rglob("*.jsonl")
    lines = trace_file.read_text(encoding="utf-8").splitlines()
    return Run(answers, [json.loads(line) for line in lines])

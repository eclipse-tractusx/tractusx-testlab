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

"""Checkpoints at the edges of a run, with the real player (ADR-0028).

A run interrupted in the middle of a test, a checkpoint whose step an ``if:``
skips, and a test ``skip_tests`` left out that a person runs anyway.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from combinations.mock_server_double import free_port
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging.trace import event_data, event_digest
from tractusx_testlab.models import TestStatus
from tractusx_testlab.player import TestlabPlayer
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks


def _select(step_id: str, *options: str) -> dict:
    return {
        "id": step_id,
        "uses": "flow/select",
        "with": {"options": list(options), "timeout_s": 10},
    }


def _package(root: Path, tests: dict[str, list[dict]], skippable: tuple[str, ...] = ()) -> Path:
    from tractusx_testlab.cli.compile import compile as compile_command

    (root / "src" / "tests").mkdir(parents=True)
    manifest = {
        "kind": "tck",
        "syntax": "v1-alpha",
        "id": "edge-tck",
        "metadata": {
            "name": "Edges",
            "version": "v1.0.0",
            "description": "d",
            "authors": [{"name": "TestLab", "email": "t@example.org", "company": "Eclipse"}],
            "copyright_holders": ["2026 Contributors to the Eclipse Foundation"],
            "license": "Apache-2.0",
            "standards": [{"id": "TESTLAB-INTERNAL", "version": "v1.0.0"}],
        },
        "tests": [
            {
                "id": f"{test_id}.yaml",
                "name": test_id,
                **({"skippable": True} if test_id in skippable else {}),
            }
            for test_id in tests
        ],
    }
    (root / "src" / "index.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    for test_id, steps in tests.items():
        test = {
            "kind": "test",
            "syntax": "v1-alpha",
            "namespace": "edge-tck",
            "id": test_id,
            "metadata": {"name": test_id, "version": "v1.0.0", "description": test_id},
            "execution": steps,
        }
        (root / "src" / "tests" / f"{test_id}.yaml").write_text(yaml.safe_dump(test), "utf-8")
    compile_command(
        manifest=root / "src" / "index.yaml",
        compiler_keys=None,
        player_pub=None,
        output=root / "dist",
        version=None,
        plain=False,
    )
    return root / "dist" / "edge-tck.tck"


@pytest.fixture
def player(tmp_path: Path):
    clear_mocks()
    clear_callback_manager()
    config = TestlabConfig(
        logs_dir=tmp_path / "logs", data_dir=tmp_path / "data", server_port=free_port()
    )
    yield TestlabPlayer(config=config)
    clear_mocks()
    clear_callback_manager()


class _Host:
    """What a host receives, answering each choice it is asked from *answers* (step id → option)."""

    def __init__(self, player: TestlabPlayer, answers: dict[str, str]) -> None:
        self.player = player
        self.answers = answers
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.on_ask: dict[str, Any] = {}
        player.monitor.add_callback(self)

    def __call__(self, event: str, payload: dict[str, Any]) -> None:
        self.events.append((event, payload))
        if event != "step.selecting":
            return
        step = payload["step_id"]
        loop = asyncio.get_running_loop()
        if step in self.answers:
            loop.call_soon(
                self.player.jobs.selections.answer, payload["job_id"], self.answers[step], step
            )
        elif step in self.on_ask:
            loop.call_soon(self.on_ask[step])

    def of(self, name: str) -> list[dict[str, Any]]:
        return [payload for event, payload in self.events if event == name]

    def index(self, step_id: str) -> int:
        (plan,) = self.of("checkpoints.planned")
        return next(i for i, c in enumerate(plan["checkpoints"]) if c["step_id"] == step_id)

    def updates(self, step_id: str) -> list[dict[str, Any]]:
        index = self.index(step_id)
        return [u["checkpoint"] for u in self.of("checkpoint.updated") if u["index"] == index]

    def states(self, step_id: str) -> list[str]:
        return [checkpoint["state"] for checkpoint in self.updates(step_id)]


def test_a_test_interrupted_mid_run_ends_cancelled_and_keeps_what_its_checkpoints_became(
    tmp_path: Path, player: TestlabPlayer
) -> None:
    """Ctrl-C (or a host dropping a run) while the second question is open."""
    tck = Loader().load(
        _package(tmp_path, {"two": [_select("first", "a", "b"), _select("second", "c", "d")]})
    )
    host = _Host(player, {"first": "a"})

    async def run() -> None:
        task = asyncio.create_task(player.run_tck(tck))
        host.on_ask["second"] = task.cancel
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())

    assert host.states("first") == ["now", "cleared"]
    assert host.states("second") == ["now", "not_reached"]
    assert host.updates("first")[-1]["answered_at"] is not None
    assert len(host.of("test.started")) == 1
    (completed,) = host.of("test.completed")
    assert completed["result"]["status"] == TestStatus.CANCELLED.value

    # The trace tells it from a test left out on purpose: failed, cut short.
    lines = _trace(tmp_path)
    ends = [
        line for line in lines if line["type"].startswith("tck.test.") and "test_id" in line["data"]
    ]
    (end,) = [line for line in ends if line["type"] != "tck.test.start"]
    assert end["type"] == "tck.test.failed"
    assert end["data"]["status"] == "CANCELLED"
    assert [error["code"] for error in end["data"]["errors"]] == ["TEST_CANCELLED"]


def test_every_id_of_a_checkpoint_run_is_the_hash_of_its_data_as_written(
    tmp_path: Path, player: TestlabPlayer
) -> None:
    """The JSONL holds no ``None`` (a checkpoint's ``asked_at`` included), and its ids recompute."""
    tck = Loader().load(_package(tmp_path, {"one": [_select("only", "a", "b")]}))
    _Host(player, {"only": "a"})
    asyncio.run(player.run_tck(tck))

    lines = _trace(tmp_path)
    (plan,) = [line for line in lines if line["type"] == "checkpoints.planned"]
    assert "asked_at" not in plan["data"]["checkpoints"][0]
    assert any(line["type"] == "checkpoint.updated" for line in lines)
    for line in lines:
        digest = line["id"].rsplit("/", 1)[1]
        assert digest == event_digest(line["data"]), line["type"]
        assert event_data(line["data"]) == line["data"]
        assert "null" not in json.dumps(line["data"])


def _trace(root: Path) -> list[dict[str, Any]]:
    (path,) = (root / "data").rglob("*.jsonl")
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def test_a_checkpoint_whose_if_says_no_was_never_asked(
    tmp_path: Path, player: TestlabPlayer
) -> None:
    gated = {
        "id": "announce",
        "uses": "util/log",
        "with": {"message": "m"},
        "checkpoint": {"label": "Announced"},
        "if": "${{ failure() }}",
    }
    tck = Loader().load(_package(tmp_path, {"gated": [gated]}))
    host = _Host(player, {})
    result = asyncio.run(player.run_tck(tck))

    assert result.status == TestStatus.COMPLETED
    assert host.states("announce") == ["skipped"]
    final = host.updates("announce")[-1]
    assert (final["attempts"], final["asked_at"]) == (0, None)


def test_a_test_skip_tests_left_out_is_followed_when_a_person_runs_it_anyway(
    tmp_path: Path, player: TestlabPlayer
) -> None:
    marked = {"id": "note", "uses": "util/log", "with": {"message": "m"}, "checkpoint": True}
    package = _package(
        tmp_path, {"first": [marked], "choice": [_select("pick", "a", "b")]}, skippable=("choice",)
    )
    tck = Loader().load(package)
    host = _Host(player, {"pick": "b"})

    async def run() -> TestStatus:
        session = await player.open_session(tck, runtime_vars={"skip_tests": ["choice.yaml"]})
        await session.run_scheduled()
        result = await session.run_test("choice.yaml")
        await session.close()
        return result.status

    assert asyncio.run(run()) == TestStatus.COMPLETED

    (plan,) = host.of("checkpoints.planned")
    briefed = [entry.step_id for entry in tck.checkpoints(["choice.yaml"])]
    assert [(c["step_id"], c["state"]) for c in plan["checkpoints"]] == [
        ("note", "ahead"),
        ("pick", "skipped"),
    ]
    assert briefed == ["note"]  # the briefing's indexes did not move
    assert host.states("pick") == ["ahead", "now", "cleared"]
    (selecting,) = host.of("step.selecting")
    assert selecting["checkpoint"]["index"] == 1

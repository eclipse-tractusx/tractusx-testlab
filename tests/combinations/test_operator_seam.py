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

"""Who answers a run: its host through the question board, or an operator (ADR-0028).

The engine runs a package with ``TestlabPlayer.run_tck`` and answers a choice on
``JobManager.selections``: nothing is asked of anyone, nothing is read from stdin.
``testlab run`` hands ``run_with_operator`` an operator instead, which approves
the checkpoints before the run starts and answers the choices while it runs —
through the same board.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml

from combinations.mock_server_double import free_port
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import TestStatus
from tractusx_testlab.models.runtime.checkpoints import CheckpointEntry
from tractusx_testlab.player import TestlabPlayer
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.player.operator import Question, RunAborted, RunDeclined, run_with_operator
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

_SELECT = {"id": "pick", "uses": "flow/select", "with": {"options": ["a", "b"], "timeout_s": 10}}
_LOG = {"id": "note", "uses": "util/log", "with": {"message": "no checkpoint here"}}


def _package(root: Path, *tests: tuple[str, list[dict]]) -> Path:
    from tractusx_testlab.cli.compile import compile as compile_command

    (root / "src" / "tests").mkdir(parents=True)
    manifest = {
        "kind": "tck",
        "syntax": "v1-alpha",
        "id": "seam-tck",
        "metadata": {
            "name": "Seam",
            "version": "v1.0.0",
            "description": "d",
            "authors": [{"name": "TestLab", "email": "t@example.org", "company": "Eclipse"}],
            "copyright_holders": ["2026 Contributors to the Eclipse Foundation"],
            "license": "Apache-2.0",
            "standards": [{"id": "TESTLAB-INTERNAL", "version": "v1.0.0"}],
        },
        "tests": [{"id": f"{test_id}.yaml", "name": test_id} for test_id, _ in tests],
    }
    (root / "src" / "index.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    for test_id, steps in tests:
        test = {
            "kind": "test",
            "syntax": "v1-alpha",
            "namespace": "seam-tck",
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
    return root / "dist" / "seam-tck.tck"


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


class _Untouchable:
    """A stdin the player must never read."""

    def __getattr__(self, name: str):
        raise AssertionError(f"the player touched stdin ({name})")


class _Operator:
    def __init__(self, approve: bool = True, answer: str | None = "b", stop: bool = False) -> None:
        self.approved: list[Sequence[CheckpointEntry]] = []
        self.questions: list[Question] = []
        self._approve, self._answer, self._stop = approve, answer, stop

    def approve(self, checkpoints: Sequence[CheckpointEntry]) -> bool:
        self.approved.append(checkpoints)
        return self._approve

    def choose(self, question: Question) -> str | None:
        self.questions.append(question)
        if self._stop:
            raise RunAborted("stopped", "quit")
        return self._answer


def test_the_engines_path_asks_nobody_and_reads_no_stdin(
    tmp_path: Path, player: TestlabPlayer, monkeypatch, capsys
) -> None:
    tck = Loader().load(_package(tmp_path, ("choose", [_SELECT])))
    monkeypatch.setattr(sys, "stdin", _Untouchable())
    events: list[tuple[str, dict]] = []

    def engine(event: str, payload: dict) -> None:  # the engine's UI, answering
        events.append((event, payload))
        if event == "step.selecting":
            asyncio.get_running_loop().call_soon(
                player.jobs.selections.answer, payload["job_id"], "a", payload["step_id"]
            )

    player.monitor.add_callback(engine)
    result = asyncio.run(player.run_tck(tck))

    assert result.status == TestStatus.COMPLETED
    out = capsys.readouterr().out
    assert "Continue?" not in out and "Choose [" not in out and "YOU CHOOSE" not in out
    (selected,) = [p for e, p in events if e == "step.selected"]
    assert selected["option"]["id"] == "a"


def test_an_operator_approves_then_answers_through_the_same_board(
    tmp_path: Path, player: TestlabPlayer
) -> None:
    tck = Loader().load(_package(tmp_path, ("choose", [_SELECT])))
    operator = _Operator()
    result = asyncio.run(run_with_operator(player, tck, operator))

    assert result.status == TestStatus.COMPLETED
    assert [[e.step_id for e in seen] for seen in operator.approved] == [["pick"]]
    (question,) = operator.questions
    assert (question.number, question.total, question.step_id) == (1, 1, "pick")
    assert [o.id for o in question.selection.options] == ["a", "b"]


def test_a_run_not_approved_starts_nothing(tmp_path: Path, player: TestlabPlayer) -> None:
    tck = Loader().load(_package(tmp_path, ("choose", [_SELECT])))
    with pytest.raises(RunDeclined):
        asyncio.run(run_with_operator(player, tck, _Operator(approve=False)))
    assert player.jobs.list_jobs() == []


def test_a_run_without_checkpoints_is_not_put_to_the_operator(
    tmp_path: Path, player: TestlabPlayer
) -> None:
    tck = Loader().load(_package(tmp_path, ("plain", [_LOG])))
    operator = _Operator(approve=False)
    result = asyncio.run(run_with_operator(player, tck, operator))
    assert result.status == TestStatus.COMPLETED and operator.approved == []


def test_an_operator_who_stops_ends_the_run_and_no_further_test_starts(
    tmp_path: Path, player: TestlabPlayer
) -> None:
    tck = Loader().load(_package(tmp_path, ("choose", [_SELECT]), ("after", [_LOG])))
    with pytest.raises(RunAborted) as stopped:
        asyncio.run(run_with_operator(player, tck, _Operator(stop=True)))
    result = stopped.value.result
    assert result is not None
    assert [test.status for test in result.tests] == [TestStatus.FAILED, TestStatus.SKIPPED]

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

"""``testlab run`` asks before it starts and when the run asks (ADR-0027).

Exit codes: 0 passed, 2 nothing to answer with, 3 not approved, 4 stopped at a
choice. ``--yes`` (or ``TESTLAB_YES``) approves, ``--choose`` answers up front.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.combinations.mock_server_double import free_port
from tractusx_testlab.cli import app
from tractusx_testlab.cli import run as run_module
from tractusx_testlab.cli._terminal_operator import TerminalOperator
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

_SELECT = {"id": "pick", "uses": "flow/select", "with": {"options": ["a", "b"], "timeout_s": 10}}
_LOG = {"id": "note", "uses": "util/log", "with": {"message": "m"}}


def _manifest(root: Path, steps: list[dict]) -> Path:
    (root / "tests").mkdir(parents=True)
    (root / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "kind": "tck",
                "syntax": "v1-alpha",
                "id": "cli-tck",
                "metadata": {
                    "name": "CLI",
                    "version": "v1.0.0",
                    "description": "d",
                    "authors": [{"name": "T", "email": "t@example.org", "company": "E"}],
                    "copyright_holders": ["2026 Contributors to the Eclipse Foundation"],
                    "license": "Apache-2.0",
                    "standards": [{"id": "TESTLAB-INTERNAL", "version": "v1.0.0"}],
                },
                "tests": [{"id": "one.yaml", "name": "one"}],
            }
        ),
        encoding="utf-8",
    )
    test = {
        "kind": "test",
        "syntax": "v1-alpha",
        "namespace": "cli-tck",
        "id": "one",
        "metadata": {"name": "one", "version": "v1.0.0", "description": "d"},
        "execution": steps,
    }
    (root / "tests" / "one.yaml").write_text(yaml.safe_dump(test), encoding="utf-8")
    return root / "index.yaml"


@pytest.fixture
def run_cli(tmp_path: Path, monkeypatch):
    """``testlab run`` on a one-test TCK of *steps*, in a directory of its own."""
    monkeypatch.chdir(tmp_path)
    clear_mocks()
    clear_callback_manager()

    def invoke(steps: list[dict], *args: str, input: str | None = None, env: dict | None = None):
        manifest = _manifest(tmp_path / "src", steps)
        environment = {"TESTLAB_SERVER_PORT": str(free_port()), **(env or {})}
        return CliRunner().invoke(app, ["run", str(manifest), *args], input=input, env=environment)

    yield invoke
    clear_mocks()
    clear_callback_manager()


@pytest.fixture
def at_a_terminal(monkeypatch) -> None:
    """As though stdin were a terminal: what is typed is the runner's input."""
    monkeypatch.setattr(
        run_module,
        "TerminalOperator",
        functools.partial(TerminalOperator, is_terminal=lambda: True),
    )


def test_without_a_terminal_and_without_yes_nothing_runs(run_cli) -> None:
    result = run_cli([_SELECT])
    assert result.exit_code == 2
    assert "THIS RUN NEEDS YOU AT 1 CHECKPOINT" in result.output
    assert "pass --yes" in result.output
    assert "TCK RUN SUMMARY" not in result.output


@pytest.mark.parametrize("approval", [["--yes"], ["-y"]])
def test_yes_approves_and_choose_answers(run_cli, approval: list[str]) -> None:
    result = run_cli([_SELECT], *approval, "--choose", "pick=2")
    assert result.exit_code == 0, result.output
    assert "Continue? [y/N]: yes (--yes)" in result.output
    assert "Choose [1-2]: b (--choose)" in result.output


def test_the_environment_approves_too(run_cli) -> None:
    result = run_cli([_SELECT], "--choose", "pick=a", env={"TESTLAB_YES": "1"})
    assert result.exit_code == 0, result.output


def test_yes_never_answers_a_choice(run_cli) -> None:
    result = run_cli([_SELECT], "--yes")
    assert result.exit_code == 2
    assert "--choose pick=<1-2|option id>" in result.output


def test_a_run_without_checkpoints_asks_nothing(run_cli) -> None:
    result = run_cli([_LOG])
    assert result.exit_code == 0, result.output
    assert "CHECKPOINT" not in result.output and "Continue?" not in result.output


@pytest.mark.usefixtures("at_a_terminal")
@pytest.mark.parametrize("answer", ["n\n", "\n"])
def test_no_or_nothing_at_the_terminal_declines(run_cli, answer: str) -> None:
    result = run_cli([_SELECT], input=answer)
    assert result.exit_code == 3
    assert "Not approved: no test runs." in result.output
    assert "TCK RUN SUMMARY" not in result.output


@pytest.mark.usefixtures("at_a_terminal")
def test_yes_then_a_number_at_the_terminal_runs_it(run_cli) -> None:
    result = run_cli([_SELECT], input="y\n5\n2\n")
    assert result.exit_code == 0, result.output
    assert "Type a number from 1 to 2, or q to stop." in result.output
    assert "Chosen: 2 b" in result.output


@pytest.mark.usefixtures("at_a_terminal")
def test_q_at_a_choice_stops_the_run_with_its_own_code(run_cli) -> None:
    result = run_cli([_SELECT, _LOG], input="y\nq\n")
    assert result.exit_code == 4
    assert "Stopped by the operator" in result.output

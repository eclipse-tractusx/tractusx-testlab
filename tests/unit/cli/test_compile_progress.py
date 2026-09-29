###############################################################
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
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""A compilation says where it is while it runs, instead of an empty console."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from tests.paths import CCM_RAW_DIR
from tractusx_testlab.cli import app
from tractusx_testlab.cli._compile_report import ConsoleProgress
from tractusx_testlab.compiler.compiler import Compiler

runner = CliRunner()


class _Recorder:
    """A CompileProgress that writes down what it heard."""

    def __init__(self) -> None:
        self.heard: list[str] = []

    def stage(self, label: str, total: int | None = None) -> None:
        self.heard.append(f"stage {label}" + (f" /{total}" if total is not None else ""))

    def item(self, label: str) -> None:
        self.heard.append(f"item {label}")

    def fail(self) -> None:
        self.heard.append("fail")

    def finish(self) -> None:
        self.heard.append("finish")


def _log() -> tuple[ConsoleProgress, io.StringIO]:
    """A progress drawn as a CI log draws it — no terminal, nothing redrawn."""
    out = io.StringIO()
    return ConsoleProgress(Console(file=out, force_terminal=False, width=200)), out


class TestTheCompilerReportsItsStages:
    def test_in_order_with_every_test_it_checks(self, tmp_path: Path) -> None:
        heard = _Recorder()

        Compiler(progress=heard).compile_plain(CCM_RAW_DIR / "index.yaml", tmp_path)

        stages = [line for line in heard.heard if line.startswith("stage ")]
        assert stages[0] == "stage Reading index.yaml"
        assert stages[1].startswith("stage Checking the tests /")
        assert stages[2:] == [
            "stage Checking the manifest and tests against the JSON schemas",
            "stage Building the execution plan and packing its assets",
        ]
        tests = [line for line in heard.heard if line.startswith("item tests/")]
        assert len(tests) == int(stages[1].rsplit("/", 1)[1]) > 0

    def test_a_compiler_nobody_watches_reports_nowhere(self, tmp_path: Path) -> None:
        manifest, _ = Compiler().compile_plain(CCM_RAW_DIR / "index.yaml", tmp_path)
        assert manifest["package"]["checksum"]


class TestTheConsole:
    def test_a_log_gets_a_line_per_finished_stage_and_per_test(self) -> None:
        progress, out = _log()
        progress.begin(Path("raw/index.yaml"))
        progress.stage("Reading index.yaml")
        progress.stage("Checking the tests", total=2)
        progress.item("tests/a.yaml")
        progress.item("tests/b.yaml")
        progress.finish()

        lines = out.getvalue().splitlines()
        assert lines[0] == "Compiling raw/index.yaml"
        assert lines[1].startswith("  ✓ Reading index.yaml")
        assert lines[2:4] == ["      1/2 tests/a.yaml", "      2/2 tests/b.yaml"]
        assert lines[4].startswith("  ✓ Checking the tests (2)")
        assert lines[4].endswith("s")

    def test_a_failed_stage_is_marked_and_ends_the_report(self) -> None:
        progress, out = _log()
        progress.stage("Checking the tests", total=1)
        progress.fail()
        progress.finish()

        lines = out.getvalue().splitlines()
        assert len(lines) == 1
        assert lines[0].startswith("  ✗ Checking the tests (1)")

    def test_a_long_path_is_one_line_in_a_log(self) -> None:
        out = io.StringIO()
        progress = ConsoleProgress(
            Console(file=out, force_terminal=False, width=40, soft_wrap=True)
        )
        progress.begin(Path("/a/very/long/path/that/does/not/fit/in/forty/columns/index.yaml"))
        assert len(out.getvalue().splitlines()) == 1


class TestTheCommand:
    def test_it_shows_every_stage_through_to_the_sealed_package(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["compile", str(CCM_RAW_DIR / "index.yaml"), "-o", str(tmp_path)]
        )

        assert result.exit_code == 0, result.output
        for stage in (
            "Compiling",
            "✓ Reading index.yaml",
            "✓ Checking the tests",
            "✓ Building the execution plan and packing its assets",
            "✓ Bundling the sources",
            "✓ Sealing the package",
            "Compiled →",
        ):
            assert stage in result.output
        assert result.output.index("✓ Sealing the package") < result.output.index("Compiled →")

    @pytest.mark.parametrize("plain", [False, True])
    def test_a_failure_marks_the_stage_it_failed_in(self, tmp_path: Path, plain: bool) -> None:
        manifest = tmp_path / "index.yaml"
        manifest.write_text("{{not valid yaml", encoding="utf-8")
        args = ["compile", str(manifest), *(["--plain"] if plain else [])]

        result = runner.invoke(app, args)

        assert result.exit_code == 1
        assert "✗ Reading index.yaml" in result.output
        assert "Compiled →" not in result.output

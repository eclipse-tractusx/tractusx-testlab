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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The end-of-run report: the SDK's summary box, with colour.

The table is the one ``tractusx_sdk.extensions.tck.connector.helpers.print_summary``
draws — 80 columns, ``✓``/``✗``/``-`` icons, RESULT and TIME columns, the
verdict in the footer — so a person who runs both tools reads one report.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import typer

from tractusx_testlab.cli._run_summary import print_run_results, render_run_results
from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.models.primitives.enums import ScriptStatus, StepStatus
from tractusx_testlab.models.runtime.results import (
    AssertionResult,
    AssertionSummary,
    ScriptResult,
    StepResult,
    TckResult,
)

GREEN, RED, YELLOW = "\x1b[32m", "\x1b[31m", "\x1b[33m"


def _step(name: str, status: StepStatus, **kw) -> StepResult:
    return StepResult(step_name=name, step_type="http/http_request", status=status, **kw)


def _result() -> TckResult:
    """Two scripts: one clean, one with a failure and a skip after it."""
    started = datetime(2026, 9, 12, 10, 0, 0)
    return TckResult(
        tck_id="demo-tck",
        status=ScriptStatus.FAILED,
        started_at=started,
        finished_at=started + timedelta(seconds=3.25),
        scripts=[
            ScriptResult(
                script_id="provision",
                script_name="provision",
                status=ScriptStatus.COMPLETED,
                total_duration_s=1.0,
                execution=[
                    _step("create_asset", StepStatus.PASSED, duration_s=0.4),
                    _step("create_policy", StepStatus.PASSED, duration_s=0.6),
                ],
                assertion_summary=AssertionSummary(declared=2, total=2, passed=2),
            ),
            ScriptResult(
                script_id="consume",
                script_name="consume",
                status=ScriptStatus.FAILED,
                total_duration_s=2.25,
                execution=[
                    _step("encode_filter", StepStatus.PASSED, duration_s=0.05),
                    _step(
                        "pull_dtr",
                        StepStatus.FAILED,
                        duration_s=2.2,
                        error="catalog request refused\n  403 from the provider",
                        assertions=[
                            AssertionResult(
                                assertion=Assertion(uses="validate/assert", name="offer is made"),
                                passed=False,
                                message="expected 1 offer, got 0",
                            )
                        ],
                    ),
                    _step("verify_twin", StepStatus.SKIPPED),
                ],
                assertion_summary=AssertionSummary(declared=3, total=1, failed_hard=1),
            ),
        ],
    )


def _plain(lines: list[str]) -> list[str]:
    return [typer.unstyle(line) for line in lines]


class TestLayout:
    def test_every_box_line_is_the_sdk_width(self) -> None:
        """Colour codes take no columns, so they must not be counted as padding."""
        for line in _plain(render_run_results(_result())):
            if line.startswith(("║", "╔", "╠", "╚")):
                assert len(line) == 80, repr(line)

    def test_one_table_per_script_then_the_run_summary(self) -> None:
        text = "\n".join(_plain(render_run_results(_result())))
        assert text.index("Script: provision") < text.index("Script: consume")
        assert text.index("Script: consume") < text.index("TEST RUN SUMMARY")
        assert text.count("STEP") == 2
        assert text.count("SCRIPT") == 1

    def test_a_step_row_has_icon_name_result_and_time(self) -> None:
        rows = [line for line in _plain(render_run_results(_result())) if "pull_dtr" in line]
        table_row = rows[0]
        assert table_row.startswith("║  ✗ pull_dtr")
        assert "FAIL" in table_row
        assert table_row.rstrip("║").rstrip().endswith("2.2s")

    def test_a_skipped_step_is_a_dash_and_no_time(self) -> None:
        rows = [line for line in _plain(render_run_results(_result())) if "verify_twin" in line]
        assert rows[0].startswith("║  - verify_twin")
        assert "SKIP" in rows[0]
        assert rows[0].rstrip("║").rstrip().endswith("-")

    def test_the_footer_counts_every_outcome(self) -> None:
        """The old line subtracted passed from total, so a skip counted as a failure."""
        plain = _plain(render_run_results(_result()))
        script_footer = next(line for line in plain if "RESULT: FAIL" in line)
        assert "1 passed  1 failed  1 skipped" in script_footer
        assert "Total: 2.2s" in script_footer
        run_footer = [line for line in plain if "RESULT: FAIL" in line][-1]
        assert "3 passed  1 failed  1 skipped" in run_footer
        assert "Total: 3.2s" in run_footer

    def test_the_run_summary_lists_scripts(self) -> None:
        plain = _plain(render_run_results(_result()))
        start = next(i for i, line in enumerate(plain) if "TEST RUN SUMMARY" in line)
        summary = "\n".join(plain[start:])
        assert "✓ provision" in summary
        assert "✗ consume" in summary

    def test_failures_are_listed_under_the_table(self) -> None:
        plain = _plain(render_run_results(_result()))
        text = "\n".join(plain)
        assert "           Error: catalog request refused" in text
        assert "                    403 from the provider" in text
        assert "           Failed: offer is made — expected 1 offer, got 0" in text
        # The detail comes after the script's table, not inside it.
        footer = next(i for i, line in enumerate(plain) if "1 passed  1 failed  1 skipped" in line)
        error = next(i for i, line in enumerate(plain) if "Error: catalog" in line)
        assert error > footer

    def test_a_long_step_name_is_cut_not_wrapped(self) -> None:
        result = _result()
        result.scripts[0].execution[0].step_name = "x" * 70
        rows = [line for line in _plain(render_run_results(result)) if "xxxx" in line]
        assert len(rows[0]) == 80
        assert "…" in rows[0]

    def test_assertion_notes_follow_each_script(self) -> None:
        text = "\n".join(_plain(render_run_results(_result())))
        assert "Assertions: 2 total, 2 passed, 0 hard-failed, 0 soft-failed" in text
        assert "WARNING: 2 declared assertion(s) were never evaluated" in text


class TestColour:
    def test_pass_fail_and_skip_are_green_red_and_yellow(self) -> None:
        lines = render_run_results(_result())
        assert GREEN in next(line for line in lines if "create_asset" in line)
        assert RED in next(line for line in lines if "pull_dtr" in line)
        assert YELLOW in next(line for line in lines if "verify_twin" in line)

    def test_the_verdict_is_coloured_and_bold(self) -> None:
        lines = render_run_results(_result())
        footer = next(line for line in lines if "RESULT: FAIL" in typer.unstyle(line))
        assert RED in footer
        assert "\x1b[1m" in footer

    def test_the_name_and_time_stay_plain(self) -> None:
        """Only the outcome is coloured; the row text is not a wall of red."""
        line = next(line for line in render_run_results(_result()) if "pull_dtr" in line)
        assert f"{RED}✗" in line
        # The text after the icon's reset and before the next colour opens is
        # the name column, uncoloured.
        after_icon = line.split("\x1b[0m", 1)[1]
        assert after_icon.split("\x1b[", 1)[0].strip() == "pull_dtr"


class TestPrinting:
    def test_colour_is_stripped_off_a_terminal_and_the_exit_code_is_the_verdict(
        self, capsys
    ) -> None:
        with pytest.raises(typer.Exit) as exit_info:
            print_run_results(_result())
        assert exit_info.value.exit_code == 1
        out = capsys.readouterr().out
        assert "\x1b" not in out
        assert "RESULT: FAIL  |  3 passed  1 failed  1 skipped" in out

    def test_a_clean_run_exits_zero(self, capsys) -> None:
        result = _result()
        result.status = ScriptStatus.COMPLETED
        with pytest.raises(typer.Exit) as exit_info:
            print_run_results(result)
        assert exit_info.value.exit_code == 0

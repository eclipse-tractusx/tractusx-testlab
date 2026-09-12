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

"""The result tables a run ends with.

Drawn the way the SDK's TCK runners draw theirs
(``tractusx_sdk.extensions.tck.connector.helpers.print_summary``): an 80-column
box, one row per step with a ``✓`` / ``✗`` / ``-`` icon, a RESULT column and a
TIME column, and the verdict with its tally in the footer. A person who runs
both tools sees one report. Colour is added on top — green for a pass, red for
a failure, yellow for a skip — and stripped by ``typer.echo`` when stdout is
not a terminal, so a transcript or a CI log keeps the words. ``FORCE_COLOR``
keeps the colour where there is no terminal but the reader renders escape
codes anyway (a GitHub Actions log); ``NO_COLOR`` drops it everywhere.

One table per test, each followed by the failures it had and its assertion
notes, then a closing table with one row per test and the run's verdict. The
frame itself is drawn by :mod:`_result_box`; this module decides what goes in
it.
"""

from __future__ import annotations

import os

import typer

from tractusx_testlab.cli._result_box import NAME_WIDTH, Row, Table, box
from tractusx_testlab.models.primitives.enums import StepStatus, TestStatus

#: How each outcome is drawn: icon, the word in the RESULT column, its colour.
_STEP_LOOK: dict[StepStatus, tuple[str, str, str]] = {
    StepStatus.PASSED: ("✓", "PASS", "green"),
    StepStatus.FAILED: ("✗", "FAIL", "red"),
    StepStatus.SKIPPED: ("-", "SKIP", "yellow"),
}
_TEST_LOOK: dict[TestStatus, tuple[str, str, str]] = {
    TestStatus.COMPLETED: ("✓", "PASS", "green"),
    TestStatus.FAILED: ("✗", "FAIL", "red"),
    TestStatus.SKIPPED: ("-", "SKIP", "yellow"),
    TestStatus.CANCELLED: ("✗", "CANCEL", "red"),
}
#: A step or test that ended in a state the table has no row style for
#: (still PENDING because the run was cut short, say) is drawn as what it is.
_UNKNOWN_LOOK = ("?", "", "white")


def print_run_results(result) -> None:
    """Print one result table per test, the run summary, and exit accordingly."""
    colour = _colour_wanted()
    for line in render_run_results(result):
        typer.echo(line, color=colour)
    raise typer.Exit(0 if result.status == TestStatus.COMPLETED else 1)


def _colour_wanted() -> bool | None:
    """Whether the report keeps its colour: the two conventions, else the terminal.

    ``typer.echo`` strips colour when stdout is not a terminal, which is right
    for a pipe and wrong for a CI runner: GitHub Actions has no terminal but
    its log viewer renders the escape codes. ``FORCE_COLOR`` (anything but
    empty or ``0``) keeps the colour there; ``NO_COLOR`` drops it anywhere and
    wins when both are set. Unset, ``None`` leaves the decision to ``typer``.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR", "0") != "0":
        return True
    return None


def render_run_results(result) -> list[str]:
    """The lines of the end-of-run report, styled for a terminal.

    Kept apart from printing so a test can check the layout and the colouring
    without capturing a terminal: ``typer.unstyle`` on a line gives the text.
    """
    tables = [*(_test_table(test) for test in result.tests), _run_table(result)]
    # One width for the whole report, so the boxes line up under each other:
    # the SDK's, or as wide as the longest name in any of them needs.
    name_width = max([NAME_WIDTH, *(len(row.name) for table in tables for row in table.rows)])
    lines: list[str] = []
    for table, test in zip(tables, [*result.tests, None], strict=True):
        lines += box(table, name_width)
        if test is not None:
            lines += _test_failures(test)
            lines += _assertion_notes(test)
    lines.append("")
    return lines


def _test_table(test) -> Table:
    """One box per test: its steps in execution order, its verdict below."""
    return Table(
        title=f"Test: {test.test_name or test.test_id}",
        first_column="STEP",
        rows=[
            Row(*_look(_STEP_LOOK, step.status), step.step_name or step.step_type, step.duration_s)
            for step in test.execution
        ],
        verdict=_look(_TEST_LOOK, test.status),
        duration_s=test.total_duration_s,
    )


def _run_table(result) -> Table:
    """The closing box: one row per test, the run's verdict and test tally."""
    return Table(
        title="TCK RUN SUMMARY",
        first_column="TEST",
        rows=[
            Row(
                *_look(_TEST_LOOK, test.status),
                test.test_name or test.test_id,
                test.total_duration_s,
            )
            for test in result.tests
        ],
        verdict=_look(_TEST_LOOK, result.status),
        duration_s=result.duration_ms / 1000 if result.duration_ms else None,
    )


def _look(table: dict, status) -> tuple[str, str, str]:
    icon, label, colour = table.get(status, _UNKNOWN_LOOK)
    return icon, label or str(getattr(status, "value", status)), colour


def _test_failures(test) -> list[str]:
    """What went wrong, listed under the table so the table stays one row a step."""
    lines: list[str] = []
    for step in test.execution:
        failed_checks = [check for check in step.assertions if not check.passed]
        if not step.error and not failed_checks:
            continue
        lines += ["", f"  {typer.style('✗', fg='red')} {step.step_name or step.step_type}"]
        if step.error:
            lines += _error_lines(step.error)
        for check in failed_checks:
            lines.append(f"           Failed: {_check_label(check)} — {check.message}")
    return lines


def _assertion_notes(test) -> list[str]:
    if not test.execution:
        # A test that never ran (skipped by the operator) checked nothing by
        # design; saying so would read as a finding.
        return []
    s = test.assertion_summary
    lines = [
        "",
        f"  Assertions: {s.total} total, {s.passed} passed, "
        f"{s.failed_hard} hard-failed, {s.failed_soft} soft-failed",
    ]
    if s.unevaluated:
        lines.append(
            f"  WARNING: {s.unevaluated} declared assertion(s) were never "
            "evaluated — this result describes less than the test asked for."
        )
    elif s.verified_nothing:
        lines.append(
            "  NOTE: this test evaluated no assertions. It exercised the "
            "steps but verified nothing about the system under test."
        )
    return lines


def _print_error(error: str) -> None:
    """Print a step's failure, keeping an explanation that runs to several lines."""
    for line in _error_lines(error):
        typer.echo(line)


def _error_lines(error: str) -> list[str]:
    """A step's failure, keeping an explanation that runs to several lines.

    A message is not always a sentence. A failure that compared two documents —
    the offers a provider made against the policy a test expects — says which
    offers and which constraints, one per line, and printing that after a
    ``Error:`` label left every line but the first hanging at column zero,
    reading as unrelated output. The continuation is indented under the label
    instead, so the whole explanation is visibly one failure.
    """
    first, *rest = error.splitlines()
    return [f"           Error: {first}", *(f"                  {line}" for line in rest)]


def _check_label(check) -> str:
    """What to call a failed check: what the author named it, else what it is.

    A step with four ``validate/assert`` entries reported four identical labels,
    so a reader could not tell which requirement had failed. Naming an assertion
    is optional, and this is where writing one pays off.
    """
    return check.assertion.name or check.assertion.uses

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
not a terminal, so a transcript or a CI log keeps the words.

One table per script, each followed by the failures it had and its assertion
notes, then a closing table with one row per script and the run's verdict.
"""

from __future__ import annotations

import typer

from tractusx_testlab.models.primitives.enums import ScriptStatus, StepStatus

#: The SDK summary box is 80 columns; the same here.
_WIDTH = 80
_COL_NAME = 45
_COL_RESULT = 6
_COL_TIME = 8
_INNER = _WIDTH - 2

#: How each outcome is drawn: icon, the word in the RESULT column, its colour.
_STEP_LOOK: dict[StepStatus, tuple[str, str, str]] = {
    StepStatus.PASSED: ("✓", "PASS", "green"),
    StepStatus.FAILED: ("✗", "FAIL", "red"),
    StepStatus.SKIPPED: ("-", "SKIP", "yellow"),
}
_SCRIPT_LOOK: dict[ScriptStatus, tuple[str, str, str]] = {
    ScriptStatus.COMPLETED: ("✓", "PASS", "green"),
    ScriptStatus.FAILED: ("✗", "FAIL", "red"),
    ScriptStatus.SKIPPED: ("-", "SKIP", "yellow"),
    ScriptStatus.CANCELLED: ("✗", "CANCEL", "red"),
}
#: A step or script that ended in a state the table has no row style for
#: (still PENDING because the run was cut short, say) is drawn as what it is.
_UNKNOWN_LOOK = ("?", "", "white")


def print_run_results(result) -> None:
    """Print one result table per script, the run summary, and exit accordingly."""
    for line in render_run_results(result):
        typer.echo(line)
    raise typer.Exit(0 if result.status == ScriptStatus.COMPLETED else 1)


def render_run_results(result) -> list[str]:
    """The lines of the end-of-run report, styled for a terminal.

    Kept apart from printing so a test can check the layout and the colouring
    without capturing a terminal: ``typer.unstyle`` on a line gives the text.
    """
    lines: list[str] = []
    for script in result.scripts:
        lines += _script_table(script)
        lines += _script_failures(script)
        lines += _assertion_notes(script)
    lines += _run_table(result)
    lines.append("")
    return lines


def _script_table(script) -> list[str]:
    """One box per script: its steps in execution order, its verdict below."""
    rows = [
        _row(*_look(_STEP_LOOK, step.status), step.step_name or step.step_type, step.duration_s)
        for step in script.execution
    ]
    verdict = _verdict(
        _look(_SCRIPT_LOOK, script.status),
        [step.status for step in script.execution],
        script.total_duration_s,
    )
    return _box(f"Script: {script.script_name or script.script_id}", "STEP", rows, verdict)


def _run_table(result) -> list[str]:
    """The closing box: one row per script, the run's verdict and step tally."""
    rows = [
        _row(
            *_look(_SCRIPT_LOOK, script.status),
            script.script_name or script.script_id,
            script.total_duration_s,
        )
        for script in result.scripts
    ]
    verdict = _verdict(
        _look(_SCRIPT_LOOK, result.status),
        [step.status for script in result.scripts for step in script.execution],
        result.duration_ms / 1000 if result.duration_ms else None,
    )
    return _box("TEST RUN SUMMARY", "SCRIPT", rows, verdict)


def _look(table: dict, status) -> tuple[str, str, str]:
    icon, label, colour = table.get(status, _UNKNOWN_LOOK)
    return icon, label or str(getattr(status, "value", status)), colour


def _box(title: str, first_column: str, rows: list[str], verdict: str) -> list[str]:
    """Frame *rows* the way the SDK's ``print_summary`` frames its steps."""
    header = f"  {first_column:<{_COL_NAME}} {'RESULT':>{_COL_RESULT}}  {'TIME':>{_COL_TIME}}"
    return [
        "",
        "╔" + "=" * _INNER + "╗",
        "║" + f"  {title}".center(_INNER) + "║",
        "╠" + "=" * _INNER + "╣",
        "║" + header.ljust(_INNER) + "║",
        "║" + ("  " + "-" * (_WIDTH - 6)).ljust(_INNER) + "║",
        *rows,
        "╠" + "=" * _INNER + "╣",
        verdict,
        "╚" + "=" * _INNER + "╝",
    ]


def _row(icon: str, label: str, colour: str, name: str, duration_s: float | None) -> str:
    """One table row: coloured icon and RESULT word, plain name and time.

    The padding is measured on the uncoloured text — the escape codes take no
    columns, and measuring them would leave every coloured row short of the
    right border.
    """
    name = _fit(name, _COL_NAME - 2)
    time = f"{duration_s:.1f}s" if duration_s is not None else "-"
    plain = f"  {icon} {name:<{_COL_NAME - 2}} {label:>{_COL_RESULT}}  {time:>{_COL_TIME}}"
    styled = (
        "  "
        + typer.style(icon, fg=colour)
        + f" {name:<{_COL_NAME - 2}} "
        + typer.style(f"{label:>{_COL_RESULT}}", fg=colour)
        + f"  {time:>{_COL_TIME}}"
    )
    return "║" + styled + " " * max(0, _INNER - len(plain)) + "║"


def _verdict(look, step_statuses: list[StepStatus], duration_s: float | None) -> str:
    """The footer line: ``RESULT: <word>``, the step tally, and the total time.

    The tally counts steps by outcome rather than subtracting passed from
    total, which is what the old summary line did — and which reported a
    skipped step as a failed one.
    """
    _, label, colour = look
    counts = {word: 0 for word in ("PASS", "FAIL", "SKIP")}
    for status in step_statuses:
        word = _STEP_LOOK.get(status, _UNKNOWN_LOOK)[1]
        if word in counts:
            counts[word] += 1
    tally = f"{counts['PASS']} passed  {counts['FAIL']} failed  {counts['SKIP']} skipped"
    total = f"Total: {duration_s:.1f}s" if duration_s is not None else "Total: -"
    plain = f"  RESULT: {label}  |  {tally}  |  {total}"
    styled = (
        "  " + typer.style(f"RESULT: {label}", fg=colour, bold=True) + f"  |  {tally}  |  {total}"
    )
    return "║" + styled + " " * max(0, _INNER - len(plain)) + "║"


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _script_failures(script) -> list[str]:
    """What went wrong, listed under the table so the table stays one row a step."""
    lines: list[str] = []
    for step in script.execution:
        failed_checks = [check for check in step.assertions if not check.passed]
        if not step.error and not failed_checks:
            continue
        lines += ["", f"  {typer.style('✗', fg='red')} {step.step_name or step.step_type}"]
        if step.error:
            lines += _error_lines(step.error)
        for check in failed_checks:
            lines.append(f"           Failed: {_check_label(check)} — {check.message}")
    return lines


def _assertion_notes(script) -> list[str]:
    if not script.execution:
        # A script that never ran (skipped by the operator) checked nothing by
        # design; saying so would read as a finding.
        return []
    s = script.assertion_summary
    lines = [
        "",
        f"  Assertions: {s.total} total, {s.passed} passed, "
        f"{s.failed_hard} hard-failed, {s.failed_soft} soft-failed",
    ]
    if s.unevaluated:
        lines.append(
            f"  WARNING: {s.unevaluated} declared assertion(s) were never "
            "evaluated — this result describes less than the script asked for."
        )
    elif s.verified_nothing:
        lines.append(
            "  NOTE: this script evaluated no assertions. It exercised the "
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
    the offers a provider made against the policy a script expects — says which
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

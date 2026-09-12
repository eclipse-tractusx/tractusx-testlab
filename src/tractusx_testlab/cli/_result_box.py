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

"""The box a result table is drawn in.

The frame the SDK's TCK runners draw
(``tractusx_sdk.extensions.tck.connector.helpers.print_summary``): 80 columns,
a centred title, a header line, one row per entry with an icon, a name, a
RESULT word and a TIME, and a footer with the verdict and its tally. This
module knows how to draw a table; what goes in one — which steps, which
tests, which words — is :mod:`_run_summary`'s business.

Every box in a report is the same width: the SDK's 80 columns, or wider when
a name needs more, so a name is never cut short. The caller measures the
longest name across all its tables and passes that width to each box.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer

#: The SDK summary box is 80 columns, with a 43-column name; the same here
#: unless a name is longer, in which case the name column and the box grow.
WIDTH = 80
NAME_WIDTH = 43
_COL_RESULT = 6
_COL_TIME = 8
#: Everything in a row that is not the name: the indent, the icon, the gaps,
#: the RESULT and TIME columns.
_ROW_FIXED = 2 + 1 + 1 + 1 + _COL_RESULT + 2 + _COL_TIME


@dataclass(frozen=True)
class Row:
    """One table row before it is laid out: what it is and how it is drawn."""

    icon: str
    label: str
    colour: str
    name: str
    duration_s: float | None


@dataclass(frozen=True)
class Table:
    title: str
    first_column: str
    rows: list[Row]
    verdict: tuple[str, str, str]
    duration_s: float | None


def box(table: Table, name_width: int) -> list[str]:
    """Frame the table the way the SDK's ``print_summary`` frames its steps."""
    inner = max(WIDTH - 2, name_width + _ROW_FIXED)
    header = (
        f"  {table.first_column:<{name_width + 2}} {'RESULT':>{_COL_RESULT}}  {'TIME':>{_COL_TIME}}"
    )
    return [
        "",
        "╔" + "=" * inner + "╗",
        "║" + f"  {table.title}".center(inner) + "║",
        "╠" + "=" * inner + "╣",
        "║" + header.ljust(inner) + "║",
        "║" + ("  " + "-" * (inner - 4)).ljust(inner) + "║",
        *(_row(row, name_width, inner) for row in table.rows),
        "╠" + "=" * inner + "╣",
        _verdict(table, inner),
        "╚" + "=" * inner + "╝",
    ]


def _row(row: Row, name_width: int, inner: int) -> str:
    """One table row: coloured icon and RESULT word, plain name and time.

    The padding is measured on the uncoloured text — the escape codes take no
    columns, and measuring them would leave every coloured row short of the
    right border.
    """
    time = f"{row.duration_s:.1f}s" if row.duration_s is not None else "-"
    plain = f"  {row.icon} {row.name:<{name_width}} {row.label:>{_COL_RESULT}}  {time:>{_COL_TIME}}"
    styled = (
        "  "
        + typer.style(row.icon, fg=row.colour)
        + f" {row.name:<{name_width}} "
        + typer.style(f"{row.label:>{_COL_RESULT}}", fg=row.colour)
        + f"  {time:>{_COL_TIME}}"
    )
    return "║" + styled + " " * max(0, inner - len(plain)) + "║"


def _verdict(table: Table, inner: int) -> str:
    """The footer line: ``RESULT: <word>``, the tally of the rows above, the total time.

    The tally counts the table's own rows by outcome — steps under a test,
    tests under the run summary — so a run that skipped eight tests says so
    rather than counting the steps those tests never ran. Counting rather than
    subtracting passed from total is what stops a skip being reported as a
    failure, which the old summary line did.
    """
    _, label, colour = table.verdict
    counts = {word: 0 for word in ("PASS", "FAIL", "SKIP")}
    for row in table.rows:
        if row.label in counts:
            counts[row.label] += 1
    tally = f"{counts['PASS']} passed  {counts['FAIL']} failed  {counts['SKIP']} skipped"
    total = f"Total: {table.duration_s:.1f}s" if table.duration_s is not None else "Total: -"
    plain = f"  RESULT: {label}  |  {tally}  |  {total}"
    styled = (
        "  " + typer.style(f"RESULT: {label}", fg=colour, bold=True) + f"  |  {tally}  |  {total}"
    )
    return "║" + styled + " " * max(0, inner - len(plain)) + "║"

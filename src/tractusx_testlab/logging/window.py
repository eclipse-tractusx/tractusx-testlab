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

"""The window the console frames a moment a person has to act in.

Every other line of a run scrolls by. When the run needs someone — a wait for
the system under test (``action_banner``), the checkpoints a run will ask for
before it starts, a choice put to the operator (``cli._checkpoint_windows``) —
it draws a window instead: ``=`` above and below, a title row with what is
asked and, on the right, how long there is; a ``-`` divider; then the body::

    ==========================================================================
      CHECKPOINT 3 of 9 · YOU CHOOSE                                4m 52s left
    --------------------------------------------------------------------------
      Pick the offer to negotiate

        1  alpha
    ==========================================================================

Pure ASCII borders, so it survives every terminal and every log file. A row
that does not fit is cut with an ellipsis, so the frame is never broken; a
paragraph is wrapped instead (:func:`wrapped`).
"""

from __future__ import annotations

import shutil
import textwrap
from collections.abc import Iterable, Sequence

#: The narrowest and the widest a window is drawn, whatever the terminal says.
MIN_WIDTH = 60
MAX_WIDTH = 100
_ELLIPSIS = "…"


def terminal_width() -> int:
    """The terminal's width, clamped to what a window is drawn at (60 to 100 columns)."""
    columns = shutil.get_terminal_size((80, 24)).columns
    return max(MIN_WIDTH, min(MAX_WIDTH, columns))


def fit(row: str, width: int) -> str:
    """*row* cut to *width* columns, an ellipsis where it was cut."""
    return row if len(row) <= width else row[: max(0, width - 1)] + _ELLIPSIS


def wrapped(text: str, width: int, indent: str = "  ") -> list[str]:
    """*text* as rows of at most *width* columns, each starting with *indent*."""
    return textwrap.wrap(
        " ".join(text.split()),
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_long_words=True,
    ) or [indent.rstrip()]


def window(
    title: str,
    body: Iterable[str] = (),
    *,
    aside: str = "",
    heading: Sequence[str] = (),
    width: int | None = None,
    cut: bool = True,
) -> list[str]:
    """The rows of a window: ``=`` rule, title (and *aside* on the right), *heading*,
    ``-`` divider, *body*, ``=`` rule.

    *width* defaults to the terminal's (:func:`terminal_width`). With *cut*,
    a row longer than the window is cut to it; without, it is kept whole — for
    a value a person has to copy, such as a URL to call.
    """
    width = width or terminal_width()
    room = width - 2 - (len(aside) + 2 if aside else 0)
    title_row = f"  {fit(title, room)}"
    if aside:
        title_row += " " * max(2, width - len(title_row) - len(aside)) + aside
    rows = [title_row, *heading, "-" * width, *body]
    return ["=" * width, *(fit(row, width) if cut else row for row in rows), "=" * width]

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

"""Showing a compilation while it runs — a spinner on the stage, a line when it ends.

``testlab compile`` used to print nothing until the package was written, so a
compile that took seconds looked like one that had hung. The compiler reports
its stages (:mod:`~tractusx_testlab.compiler.progress`); this draws them:

    Compiling raw/index.yaml
      ✓ Reading index.yaml                                     0.0s
      ✓ Checking the tests (5)                                 0.4s
      ⠼ Checking the manifest and tests against the JSON schemas

In a terminal the stage under way spins, and the test being checked is named
next to it. Anywhere else — a CI log — nothing redraws: each test gets a line
as it is checked, and each stage its ✓ line when it ends. It is written to
stderr, so the summary on stdout reads as it did.

Colour follows the run report's rule (``_run_summary._colour_wanted``): a
terminal gets it, ``FORCE_COLOR`` keeps it in a CI log — without the spinner,
which only a real terminal gets — and ``NO_COLOR`` drops it everywhere.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from tractusx_testlab.cli._run_summary import _colour_wanted

if TYPE_CHECKING:
    from tractusx_testlab.compiler.compiler import Compiler


def compile_or_exit(
    compiler: Compiler, manifest: Path, output_path: Path, version: str | None
) -> tuple[dict, dict]:
    """Compile *manifest* into *output_path*, or mark the stage failed and exit 1."""
    try:
        return compiler.compile_plain(
            manifest_path=manifest, output_path=output_path, version=version
        )
    except (ValueError, FileNotFoundError) as exc:
        compiler.progress.fail()
        typer.secho(
            f"Compilation failed: {exc}", fg=typer.colors.RED, err=True, color=_colour_wanted()
        )
        raise typer.Exit(1) from exc


def compiled(text: str) -> None:
    """Print the line that names the package written — in green, where colour is wanted."""
    typer.secho(text, fg=typer.colors.GREEN, bold=True, color=_colour_wanted())


#: The column the stage timings line up on.
_LABEL_WIDTH = 58


class ConsoleProgress:
    """A :class:`~tractusx_testlab.compiler.progress.CompileProgress` drawn on stderr."""

    __slots__ = ("_console", "_count", "_label", "_live", "_started", "_status", "_total")

    def __init__(self, console: Any = None) -> None:
        from rich.console import Console

        terminal = sys.stderr.isatty()
        colour = _colour_wanted()
        # Soft wrap: a path or a label longer than the log's 80 columns is one
        # line in a log, not two.
        self._console = console or Console(
            stderr=True,
            force_terminal=terminal or colour is True,
            no_color=colour is False,
            soft_wrap=True,
        )
        # Only a real terminal redraws: FORCE_COLOR makes rich think it has one.
        self._live = terminal if console is None else self._console.is_terminal
        self._status: Any = None
        self._label: str | None = None
        self._total: int | None = None
        self._count = 0
        self._started = 0.0

    def begin(self, manifest: Path) -> None:
        """Say what is being compiled, before the first stage."""
        relative = os.path.relpath(manifest)
        shown = relative if not relative.startswith("..") else str(manifest)
        self._console.print(f"[bold cyan]Compiling[/] [bold]{shown}[/]", highlight=False)

    def stage(self, label: str, total: int | None = None) -> None:
        self._end("green", "✓")
        self._label, self._total, self._count = label, total, 0
        self._started = time.monotonic()
        if self._live:
            self._status = self._console.status(self._describe(), spinner="dots")
            self._status.start()

    def item(self, label: str) -> None:
        self._count += 1
        if self._status is not None:
            self._status.update(self._describe(label))
        elif not self._live:
            self._console.print(f"      [dim]{self._position()}{label}[/]", highlight=False)

    def finish(self) -> None:
        self._end("green", "✓")

    def fail(self) -> None:
        self._end("red", "✗")

    def _end(self, colour: str, mark: str) -> None:
        """Close the stage under way with *mark*, in *colour*, and how long it took."""
        if self._label is None:
            return
        if self._status is not None:
            self._status.stop()
            self._status = None
        seconds = time.monotonic() - self._started
        counted = f" ({self._total})" if self._total is not None else ""
        label = f"{self._label}{counted}".ljust(_LABEL_WIDTH)
        # A failed stage is red all along; a finished one keeps the colour in its mark.
        text = f"[{colour}]{label}[/]" if colour == "red" else label
        self._console.print(
            f"  [bold {colour}]{mark}[/] {text} [dim]{seconds:5.1f}s[/]", highlight=False
        )
        self._label = None

    def _describe(self, item: str | None = None) -> str:
        """The spinner's text: the stage, and the item it is on."""
        text = f"[bold]{self._label}[/]"
        if item:
            text += f" [dim]· {self._position()}{item}[/dim]"
        return text

    def _position(self) -> str:
        """``2/5 `` while the stage knows how many items it has."""
        return f"{self._count}/{self._total} " if self._total else ""

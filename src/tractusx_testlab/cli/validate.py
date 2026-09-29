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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""CLI command for TCK manifest validation."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from tractusx_testlab.cli import app
from tractusx_testlab.cli._run_summary import _colour_wanted
from tractusx_testlab.syntax import diagnostics


@app.command()
def validate(
    manifest: Path = typer.Argument(..., help="Path to the TCK manifest (index.yaml)."),
    version: str | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Connector version for version-specific validation (e.g. 'saturn').",
    ),
) -> None:
    """Validate a TCK manifest and its tests without compiling."""
    from tractusx_testlab.cli._compile_report import ConsoleProgress
    from tractusx_testlab.compiler.compiler import Compiler

    progress = ConsoleProgress()
    progress.begin(manifest)
    compiler = Compiler(progress=progress)
    try:
        result = compiler.validate(manifest, version=version)
    except (ValueError, yaml.YAMLError) as exc:
        progress.fail()
        # A manifest that does not parse is the author's problem to fix, not a
        # crash to report: nothing downstream can run, so it is the only
        # finding there is, and a traceback of our own call stack buries it.
        message = exc if isinstance(exc, ValueError) else diagnostics.unparseable(exc, manifest)
        _say(f"  {_mark('error')} {message}")
        _say(typer.style("\nInvalid — 1 error(s)", fg=typer.colors.RED, bold=True))
        raise typer.Exit(1) from exc

    progress.finish()
    if not result.issues:
        _say(typer.style(f"OK — {manifest.name} is valid (no issues)", fg=typer.colors.GREEN))
        raise typer.Exit(0)

    for issue in result.issues:
        _say(f"  {_mark(issue.level)}{_where(issue)} {issue.message}")

    if result.valid:
        _say(typer.style(f"\nValid with {len(result.issues)} warning(s)", fg=typer.colors.YELLOW))
        raise typer.Exit(0)
    else:
        errors = sum(1 for issue in result.issues if issue.level == "error")
        _say(typer.style(f"\nInvalid — {errors} error(s)", fg=typer.colors.RED, bold=True))
        raise typer.Exit(1)


def _mark(level: str) -> str:
    """``[ERROR]`` in red or ``[WARN ]`` in yellow — the colour is dropped where it is not wanted."""
    if level == "error":
        return typer.style("[ERROR]", fg=typer.colors.RED, bold=True)
    return typer.style("[WARN ]", fg=typer.colors.YELLOW, bold=True)


def _say(line: str) -> None:
    """Print *line*, keeping its colour by the run report's rule (``_colour_wanted``)."""
    typer.echo(line, color=_colour_wanted())


def _where(issue: object) -> str:
    """Locate an issue as the author would: which phase, which step in it.

    The index alone was ambiguous — a setup step 0, an execution step 0 and a
    teardown step 0 all printed as "(step 0)", and the phase was on the issue
    the whole time.
    """
    index = getattr(issue, "step_index", None)
    if index is None:
        return ""
    phase = getattr(issue, "phase", None)
    return f" ({phase} step {index})" if phase else f" (step {index})"

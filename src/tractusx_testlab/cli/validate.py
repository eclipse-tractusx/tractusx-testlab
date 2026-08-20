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

"""CLI command for YAML test-script validation."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from tractusx_testlab.cli import app
from tractusx_testlab.syntax import diagnostics


@app.command()
def validate(
    script: Path = typer.Argument(..., help="Path to the YAML test script."),
    version: str | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Connector version for version-specific validation (e.g. 'saturn').",
    ),
) -> None:
    """Validate a YAML test script without compiling."""
    from tractusx_testlab.compiler.compiler import Compiler

    compiler = Compiler()
    try:
        result = compiler.validate(script, version=version)
    except (ValueError, yaml.YAMLError) as exc:
        # A manifest that does not parse is the author's problem to fix, not a
        # crash to report: nothing downstream can run, so it is the only
        # finding there is, and a traceback of our own call stack buries it.
        message = exc if isinstance(exc, ValueError) else diagnostics.unparseable(exc, script)
        typer.echo(f"  [ERROR] {message}")
        typer.echo("\nInvalid — 1 error(s)")
        raise typer.Exit(1) from exc

    if not result.issues:
        typer.echo(f"OK — {script.name} is valid (no issues)")
        raise typer.Exit(0)

    for issue in result.issues:
        prefix = "ERROR" if issue.level == "error" else "WARN "
        typer.echo(f"  [{prefix}]{_where(issue)} {issue.message}")

    if result.valid:
        typer.echo(f"\nValid with {len(result.issues)} warning(s)")
        raise typer.Exit(0)
    else:
        errors = sum(1 for issue in result.issues if issue.level == "error")
        typer.echo(f"\nInvalid — {errors} error(s)")
        raise typer.Exit(1)


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

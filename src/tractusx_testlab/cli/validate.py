#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
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

from tractusx_testlab.cli import app


@app.command()
def validate(
    script: Path = typer.Argument(..., help="Path to the YAML test script."),
    version: str | None = typer.Option(
        None, "--version", "-v",
        help="Connector version for version-specific validation (e.g. 'saturn').",
    ),
) -> None:
    """Validate a YAML test script without compiling."""
    from tractusx_testlab.compiler.compiler import Compiler

    compiler = Compiler()
    result = compiler.validate(script, version=version)

    if not result.issues:
        typer.echo(f"OK — {script.name} is valid (no issues)")
        raise typer.Exit(0)

    for issue in result.issues:
        prefix = "ERROR" if issue.level == "error" else "WARN "
        loc = f" (step {issue.step_index})" if issue.step_index is not None else ""
        typer.echo(f"  [{prefix}]{loc} {issue.message}")

    if result.valid:
        typer.echo(f"\nValid with {len(result.issues)} warning(s)")
        raise typer.Exit(0)
    else:
        errors = sum(1 for issue in result.issues if issue.level == "error")
        typer.echo(f"\nInvalid — {errors} error(s)")
        raise typer.Exit(1)

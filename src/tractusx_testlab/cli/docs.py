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

"""CLI command for generating the step reference page from the step contracts."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from tractusx_testlab.cli import app
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.scripting.step_docs import render_catalog

_DEFAULT_OUTPUT = Path("docs/specification/reference/steps.md")


@app.command("docs")
def docs(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help=f"Write the page to this path (default: {_DEFAULT_OUTPUT}). Use '-' for stdout.",
    ),
    step: list[str] | None = typer.Option(
        None,
        "--step",
        "-s",
        help="Document only these step types. Repeatable. Defaults to all registered steps.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the raw contracts as JSON Schema instead of Markdown.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Exit non-zero if the file on disk differs from what would be generated.",
    ),
) -> None:
    """Generate the step reference from the steps' declared input/output models."""

    if step:
        _reject_unknown_steps(step)

    content = _as_json(step) if as_json else render_catalog(step)
    target = output or _DEFAULT_OUTPUT

    if str(output) == "-":
        typer.echo(content)
        return

    if check:
        _check_up_to_date(target, content)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote {target}")


def _reject_unknown_steps(step_types: list[str]) -> None:
    unknown = sorted(set(step_types) - set(StepRegistry.list_step_types()))
    if unknown:
        typer.echo(f"Error: unknown step type(s): {', '.join(unknown)}", err=True)
        raise typer.Exit(1)


def _as_json(step_types: list[str] | None) -> str:
    """Render every step's contract as a JSON Schema document."""
    names = sorted(step_types or StepRegistry.list_step_types())
    contracts = []
    for name in names:
        step_cls = StepRegistry.get_any(name)
        if step_cls is not None:
            contracts.append(step_cls.describe().model_dump(exclude_none=True))
    return json.dumps(contracts, indent=2) + "\n"


def _check_up_to_date(target: Path, content: str) -> None:
    """Fail when the committed page no longer matches the code."""
    if not target.exists():
        typer.echo(f"Error: {target} does not exist; run 'testlab docs'.", err=True)
        raise typer.Exit(1)
    if target.read_text(encoding="utf-8") != content:
        typer.echo(f"Error: {target} is out of date; run 'testlab docs'.", err=True)
        raise typer.Exit(1)
    typer.echo(f"{target} is up to date")

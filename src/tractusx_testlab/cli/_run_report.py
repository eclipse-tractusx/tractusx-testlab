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

"""Rendering a run for a person watching it.

Split from :mod:`tractusx_testlab.cli.run` on the same seam as
``_inspect_report``: that module decides what to run, this one decides what the
terminal shows while it does — the header and the live progress bar. What
it shows once the run is over, the result tables, is :mod:`_run_summary`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer


def print_run_header(
    target: Path,
    config_file: Path | None,
    config,
    runtime_vars: dict[str, str],
    total_steps: int,
) -> None:
    """Print the banner with run configuration details."""
    width = 76
    typer.echo()
    typer.echo("=" * width)
    typer.echo(f"  Testlab Runner — {target.name}")
    typer.echo("=" * width)
    typer.echo(f"  Target:   {target}")
    if config_file:
        typer.echo(f"  Config:   {config_file}")
    typer.echo(f"  Logs dir: {config.logs_dir}")
    typer.echo(f"  Data dir: {config.data_dir}")
    if runtime_vars:
        typer.echo(f"  Vars:     {', '.join(runtime_vars.keys())}")
    typer.echo(f"  Steps:    {total_steps}")
    typer.echo()


def execute_with_progress(
    player, tck, runtime_vars: dict[str, str], total_steps: int, run_id: str | None = None
):
    """Run the TCK with a rich progress bar and return the result."""
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=progress_console(),
    ) as progress:
        task_id = progress.add_task("Starting...", total=total_steps)
        player.monitor.add_callback(_make_progress_callback(progress, task_id))
        return asyncio.run(player.run_tck(tck, runtime_vars=runtime_vars or None, job_id=run_id))


def progress_console():
    """The console the live progress bar draws on: a terminal only when there is one.

    ``rich`` reads ``FORCE_COLOR`` as "treat stdout as a terminal", which is
    the wrong reading for a live display. The e2e workflow sets it so the
    result tables keep their colour in the Actions log, and with the default
    console that also switched on the live rendering: the spinner redrawn
    between every log line, the cursor hidden, and every line of the run's
    log routed through the display and wrapped at 80 columns. Whether the
    bar animates is decided by the real terminal, so the log stays a log.
    """
    from rich.console import Console

    return Console(force_terminal=sys.stdout.isatty())


def _make_progress_callback(progress, task_id):
    """Create a progress callback for the player monitor."""

    def _on_progress(event: str, payload: dict) -> None:
        if event == "step.started":
            progress.update(task_id, description=f"  Running: {payload.get('step_type') or ''}")
        elif event == "step.completed":
            # The outcome lives on the event's nested `result`, not at the top
            # level. Reading `payload["status"]` found nothing, so the comparison
            # was never true and every step — passing or not — rendered red FAIL
            # with a blank name, on every run. The typed-event fix that removes
            # this class of guesswork is P4 (F-C02); this is the reading bug.
            step = payload.get("result") or {}
            passed = str(step.get("status", "")).upper() == "PASSED"
            icon = "[green]PASS" if passed else "[red]FAIL"
            progress.update(task_id, advance=1, description=f"  {icon} {step.get('step_name', '')}")
        elif event == "test.started":
            progress.update(task_id, description=f"  Test: {payload.get('test_id', '')}")

    return _on_progress

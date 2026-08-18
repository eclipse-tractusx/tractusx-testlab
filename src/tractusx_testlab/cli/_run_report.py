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
terminal shows while it does — the header, the live progress bar, and the
per-script result tables.
"""

from __future__ import annotations

import asyncio
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
    if runtime_vars:
        typer.echo(f"  Vars:     {', '.join(runtime_vars.keys())}")
    typer.echo(f"  Steps:    {total_steps}")
    typer.echo()


def execute_with_progress(player, tck, runtime_vars: dict[str, str], total_steps: int):
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
    ) as progress:
        task_id = progress.add_task("Starting...", total=total_steps)
        player.monitor.add_callback(_make_progress_callback(progress, task_id))
        return asyncio.run(player.run_tck(tck, runtime_vars=runtime_vars or None))


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
        elif event == "script.started":
            progress.update(task_id, description=f"  Script: {payload.get('script', '')}")

    return _on_progress


def print_run_results(result, step_status_cls, script_status_cls) -> None:
    """Print per-script step results and the final summary line."""
    width = 76

    for script in result.scripts:
        _print_script_result(script, step_status_cls)

    status_label = "PASS" if result.status == script_status_cls.COMPLETED else "FAIL"
    typer.echo()
    typer.echo("-" * width)
    if result.duration_ms:
        typer.echo(
            f"  RESULT: {status_label}  |  "
            f"{result.steps_passed} passed  "
            f"{result.steps_total - result.steps_passed} failed  |  "
            f"Duration: {result.duration_ms:.0f}ms"
        )
    else:
        typer.echo(f"  RESULT: {status_label}")
    typer.echo("=" * width)
    typer.echo()

    raise typer.Exit(0 if result.status == script_status_cls.COMPLETED else 1)


def _print_script_result(script, step_status_cls) -> None:
    """Print results for a single script."""
    typer.echo(f"  Script: {script.script_name}")
    typer.echo(f"  Status: {script.status.value}")
    if script.total_duration_s is not None:
        typer.echo(f"  Duration: {script.total_duration_s:.1f}s")
    typer.echo()

    for step in script.execution:
        icon = "PASS" if step.status == step_status_cls.PASSED else "FAIL"
        duration = f"{step.duration_s:.2f}s" if step.duration_s else "---"
        typer.echo(f"    [{icon}] {step.step_name:<50} {duration}")
        if step.error:
            typer.echo(f"           Error: {step.error}")

    if script.assertion_summary:
        s = script.assertion_summary
        typer.echo(
            f"\n    Assertions: {s.total} total, "
            f"{s.passed} passed, "
            f"{s.failed_hard} hard-failed, "
            f"{s.failed_soft} soft-failed"
        )
        if s.unevaluated:
            typer.echo(
                f"    WARNING: {s.unevaluated} declared assertion(s) were never "
                f"evaluated — this result describes less than the script asked for."
            )
        elif s.verified_nothing:
            typer.echo(
                "    NOTE: this script evaluated no assertions. It exercised the "
                "steps but verified nothing about the system under test."
            )

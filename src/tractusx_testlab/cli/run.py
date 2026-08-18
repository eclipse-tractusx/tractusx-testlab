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

"""CLI command for executing TCKs."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from tractusx_testlab.cli import app


@app.command()
def run(
    target: Path = typer.Argument(..., help="A TCK manifest (.yaml) or a compiled package (.tck)."),
    config_file: Path | None = typer.Option(
        None, "--config", "-c",
        help="YAML config file with variable overrides (e.g. saturn_tck_int.yaml).",
    ),
    player_keys: Path | None = typer.Option(
        None, "--player-keys", "-k",
        help="Directory with the player identity (required for encrypted packages).",
    ),
    compiler_pub: Path | None = typer.Option(
        None, "--compiler-pub",
        help="Path to the compiler's signing.pub (required for encrypted packages).",
    ),
    var: list[str] | None = typer.Option(
        None, "--var",
        help="Runtime variable override as KEY=VALUE. Can be repeated.",
    ),
    logs_dir: Path | None = typer.Option(
        None, "--logs-dir", "-l",
        help="Directory for log output. Defaults to ./logs in the current directory.",
    ),
) -> None:
    """Load and execute a TCK, printing results to stdout."""
    # Register all local step executors (triggers @step() decorators)
    from tractusx_testlab.config.loader import ConfigLoader
    from tractusx_testlab.models import ScriptStatus, StepStatus
    from tractusx_testlab.player.execution.player import TestlabPlayer

    runtime_vars = _build_runtime_vars(config_file, var)

    # Through the loader, so `testlab.config.yaml` and every TESTLAB_* variable
    # — the engine's infrastructure bindings among them — reach a CLI run the
    # same way they reach the server. The log directory stays a CLI decision.
    config = ConfigLoader.load(
        cli_overrides={"logs_dir": logs_dir or Path.cwd() / "logs"},
    )
    player = TestlabPlayer(config=config)

    try:
        tck = _load_tck(target, player_keys, compiler_pub)
    except ValueError as exc:
        # A package that fails verification is a security outcome, not a stack
        # trace: the operator needs to see which package was refused and why.
        typer.echo(f"\nRefused to run {target.name}:\n  {exc}", err=True)
        raise typer.Exit(1) from exc
    total_steps = tck.total_steps()

    _print_run_header(target, config_file, config, runtime_vars, total_steps)

    result = _execute_with_progress(player, tck, runtime_vars, total_steps)

    _print_run_results(result, StepStatus, ScriptStatus)


def _compile_target_for_run(target: Path, build_dir: Path) -> Path:
    """Compile a YAML target into *build_dir* and return the package to run.

    Built somewhere temporary rather than beside the manifest. ``run`` used to
    leave a ``.tck`` in the user's source tree — and in CI, in the checkout — as
    a side effect of a verb that only says it runs something.
    """
    if target.suffix == ".tck":
        return target

    from tractusx_testlab.cli.compile import compile as compile_command

    typer.echo(f"Preparing run package from {target} ...")
    compile_command(
        script=target,
        compiler_keys=None,
        player_pub=None,
        output=build_dir,
        version=None,
        plain=False,
    )
    built = sorted(build_dir.glob("*.tck"))
    if not built:
        typer.echo(f"Error: compiling {target} produced no package.", err=True)
        raise typer.Exit(1)
    return built[0]


def _build_runtime_vars(
    config_file: Path | None,
    var_overrides: list[str] | None,
) -> dict[str, str]:
    """Merge variables from config file (lower priority) and --var flags (higher priority)."""
    runtime_vars: dict[str, str] = {}

    if config_file is not None:
        runtime_vars = _load_config_variables(config_file)

    if var_overrides:
        _apply_var_overrides(runtime_vars, var_overrides)

    return runtime_vars


def _load_config_variables(config_file: Path) -> dict[str, str]:
    """Load runtime variables from a config YAML file."""
    import yaml as _yaml

    if not config_file.exists():
        typer.echo(f"Error: config file not found: {config_file}", err=True)
        raise typer.Exit(1)

    with open(config_file, encoding="utf-8") as config_handle:
        config_data = _yaml.safe_load(config_handle) or {}

    result: dict[str, str] = {}
    variables = config_data.get("variables", {})
    for var_name, var_def in variables.items():
        if isinstance(var_def, dict) and var_def.get("default") is not None:
            result[var_name] = str(var_def["default"])
        elif not isinstance(var_def, dict):
            result[var_name] = str(var_def)
    return result


def _apply_var_overrides(runtime_vars: dict[str, str], var_overrides: list[str]) -> None:
    """Apply --var KEY=VALUE overrides to the runtime vars dict."""
    for entry in var_overrides:
        if "=" not in entry:
            typer.echo(f"Invalid --var format (expected KEY=VALUE): {entry}", err=True)
            raise typer.Exit(1)
        key, value = entry.split("=", 1)
        runtime_vars[key] = value


def _load_tck(
    target: Path,
    player_keys: Path | None,
    compiler_pub: Path | None,
):
    """Load a TCK from a YAML manifest or a .tck package, plain or encrypted."""
    from tractusx_testlab.player.loading.loader import Loader

    loader = Loader()

    priv = pub = None
    if player_keys:
        from tractusx_testlab.security.crypto.keygen import load_private_key
        priv = load_private_key(player_keys / "encryption.pem")
    if compiler_pub:
        from tractusx_testlab.security.crypto.keygen import load_public_key
        pub = load_public_key(compiler_pub)

    return loader.load(target, player_private_key=priv, compiler_public_key=pub)


def _print_run_header(
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


def _execute_with_progress(player, tck, runtime_vars: dict[str, str], total_steps: int):
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
        return asyncio.run(
            player.run_tck(tck, runtime_vars=runtime_vars or None)
        )


def _make_progress_callback(progress, task_id):
    """Create a progress callback for the player monitor."""
    def _on_progress(event: str, payload: dict) -> None:
        if event == "step.started":
            progress.update(
                task_id, description=f"  Running: {payload.get('step_type') or ''}"
            )
        elif event == "step.completed":
            # The outcome lives on the event's nested `result`, not at the top
            # level. Reading `payload["status"]` found nothing, so the comparison
            # was never true and every step — passing or not — rendered red FAIL
            # with a blank name, on every run. The typed-event fix that removes
            # this class of guesswork is P4 (F-C02); this is the reading bug.
            step = payload.get("result") or {}
            passed = str(step.get("status", "")).upper() == "PASSED"
            icon = "[green]PASS" if passed else "[red]FAIL"
            progress.update(
                task_id, advance=1, description=f"  {icon} {step.get('step_name', '')}"
            )
        elif event == "script.started":
            progress.update(task_id, description=f"  Script: {payload.get('script', '')}")
    return _on_progress


def _print_run_results(result, step_status_cls, script_status_cls) -> None:
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
            f"{result.passed} passed  "
            f"{result.total - result.passed} failed  |  "
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

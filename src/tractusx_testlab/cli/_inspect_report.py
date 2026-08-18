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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Rendering the sections of ``testlab inspect`` for a person to read.

Kept apart from the command so that what is reported and how it is displayed
move independently: :mod:`tractusx_testlab.cli.inspect` decides which sections
to gather, this module decides what they look like on a terminal.
"""

from __future__ import annotations

from pathlib import Path

import typer

WIDTH = 72


def print_manifest(manifest: dict) -> None:
    """Print the manifest the package carries — what ``compile info`` printed."""
    security = manifest.get("security") or {}
    typer.echo("  MANIFEST")
    typer.echo(f"  {'TCK':<20} {manifest.get('tck', {}).get('id', '-')}")
    typer.echo(f"  {'Checksum':<20} {manifest.get('package', {}).get('checksum', '-')}")
    typer.echo(f"  {'Encrypted':<20} {'yes' if security else 'no'}")
    if security:
        typer.echo(f"  {'Signed by':<20} {security.get('compiler_id', '-')}")
        typer.echo(f"  {'Players':<20} {len(security.get('authorized_players', []))}")
    typer.echo()
    typer.echo("=" * 72)
    typer.echo()


def print_inspection(package: Path, result: object) -> None:
    """Print a human-readable inspection report."""
    from tractusx_testlab.models.runtime.inspection import TckInspectionResult

    r: TckInspectionResult = result  # type: ignore[assignment]

    typer.echo()
    typer.echo("=" * WIDTH)
    typer.echo(f"  Testlab Inspect — {package.name}")
    typer.echo("=" * WIDTH)
    typer.echo(f"  Name             : {r.name}")
    typer.echo(f"  Total Steps      : {r.total_steps}")
    typer.echo(f"  Total Validations: {r.total_validations}")
    typer.echo(f"  Scripts          : {len(r.scripts)}")
    typer.echo()

    for script in r.scripts:
        skippable_label = "Yes" if script.skippable else "No"
        typer.echo(f"  Script: {script.name}  |  ID: {script.test_id}  |  Skippable: {skippable_label}")
        typer.echo(f"  {'Step Name':<40} {'Uses':<35} {'Phase':<10} {'Validations'}")
        typer.echo(f"  {'-'*40} {'-'*35} {'-'*10} {'-'*11}")

        for step in script.steps:
            phase_label = step.phase.value.title()
            name_col = step.step_name[:39]
            uses_col = step.uses[:34]
            typer.echo(
                f"  {name_col:<40} {uses_col:<35} {phase_label:<10} {step.validation_count}"
            )

        typer.echo()

    typer.echo("=" * WIDTH)
    typer.echo()


def print_variables(tck: object) -> None:
    """Print a human-readable variables table."""
    variables = tck.all_variables()  # type: ignore[attr-defined]
    typer.echo("  VARIABLES")
    typer.echo(f"  {'ID':<30} {'Source':<12} {'Scope':<10} {'Type'}")
    typer.echo(f"  {'-'*30} {'-'*12} {'-'*10} {'-'*10}")
    for name, var in variables.items():
        scope = var.scope.value if var.scope else "—"
        typer.echo(f"  {name:<30} {var.source.value:<12} {scope:<10} {var.type}")
    typer.echo()
    typer.echo("=" * WIDTH)
    typer.echo()


def print_infrastructure(tck: object) -> None:
    """Print a human-readable infrastructure requirements table."""
    infra = tck.infrastructure_requirements()  # type: ignore[attr-defined]
    typer.echo("  INFRASTRUCTURE")
    typer.echo(f"  {'Capability':<25} {'Required':<10} {'Standard'}")
    typer.echo(f"  {'-'*25} {'-'*10} {'-'*20}")
    for cap, req in infra.engine.items():
        std = req.standard.id if req.standard else "—"
        typer.echo(f"  engine.{cap:<18} {req.required!s:<10} {std}")
    for cap, req in infra.sut.items():
        std = req.standard.id if req.standard else "—"
        typer.echo(f"  sut.{cap:<21} {req.required!s:<10} {std}")
    typer.echo()
    typer.echo("=" * WIDTH)
    typer.echo()

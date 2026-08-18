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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""CLI command for showing the configuration the engine actually resolved."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from tractusx_testlab.cli import app
from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.infrastructure.mapping import ENV_PREFIX


@app.command("config")
def config(
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="Read this file instead of searching the usual places."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit the resolved settings as JSON."),
) -> None:
    """Show the settings this engine resolved, and which of them came from the environment.

    Precedence questions — "why is it writing packages *there*?" — are otherwise
    answered by reading three sources and guessing which won.
    """
    settings = ConfigLoader.load(config_path=config_file)

    if as_json:
        typer.echo(settings.model_dump_json(indent=2))
        return

    from_env = sorted(name for name in os.environ if name.startswith(ENV_PREFIX))

    typer.echo("Resolved configuration:\n")
    for field, value in settings.model_dump(mode="json").items():
        if field == "infrastructure":
            continue
        typer.echo(f"  {field:20} {json.dumps(value) if isinstance(value, dict) else value}")

    bound = {key: val for key, val in _flat_infrastructure(settings).items() if val}
    typer.echo(f"\nInfrastructure bindings ({len(bound)} bound):")
    for key, value in sorted(bound.items()):
        typer.echo(f"  {key:52} {value}")
    if not bound:
        typer.echo("  none — a TCK requiring any capability will refuse to run")

    typer.echo(f"\nSet in the environment ({len(from_env)}):")
    for name in from_env:
        typer.echo(f"  {name}")
    if not from_env:
        typer.echo(f"  none — no {ENV_PREFIX}* variables are set")


def _flat_infrastructure(settings: object) -> dict[str, str]:
    from tractusx_testlab.infrastructure.mapping import flatten

    return flatten(settings.infrastructure)  # type: ignore[attr-defined]

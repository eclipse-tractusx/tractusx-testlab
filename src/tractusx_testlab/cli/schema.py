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

"""CLI command for generating the TCK JSON Schemas from the authoring models."""

from __future__ import annotations

from pathlib import Path

import typer

from tractusx_testlab.cli import app
from tractusx_testlab.compiler import schema_export


@app.command("schema")
def schema(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Directory to write the schemas to (default: the packaged schemas/).",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Exit non-zero if the committed schemas differ from the models.",
    ),
) -> None:
    """Generate the TCK JSON Schemas from the authoring models.

    The schemas are the published contract the IDE validates against. They used
    to be hand-written and had drifted from the models that actually run — the
    same document could be valid to one and invalid to the other.
    """
    if check:
        outdated = schema_export.stale(output)
        if outdated:
            typer.echo(
                f"Error: {', '.join(outdated)} no longer match the authoring models. "
                f"Run 'testlab schema'.",
                err=True,
            )
            raise typer.Exit(1)
        typer.echo("JSON Schemas are up to date")
        return

    for path in schema_export.write_all(output):
        typer.echo(f"Wrote {path}")

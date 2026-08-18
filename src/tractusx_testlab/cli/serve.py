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

"""CLI command for starting the Testlab mock server."""

from __future__ import annotations

import typer

from tractusx_testlab.cli import app


@app.command()
def serve(
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        help="Bind address for the server.",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to listen on.",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload for development.",
    ),
) -> None:
    """Start the Testlab FastAPI mock server via uvicorn."""
    import uvicorn

    typer.echo(f"Starting Testlab server on {host}:{port} (reload={reload})")

    uvicorn.run(
        "tractusx_testlab.server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )

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

"""CLI command for key-pair generation."""

from __future__ import annotations

from pathlib import Path

import typer

from tractusx_testlab.cli import app


@app.command()
def keygen(
    out_dir: Path = typer.Option(
        Path(".keys"),
        "--out-dir", "-o",
        help="Directory to write key pairs into.",
    ),
    label: str = typer.Option(
        "default",
        "--label", "-l",
        help="Label prefix for the key files (e.g. 'compiler', 'player').",
    ),
    override_keys: bool = typer.Option(
        False,
        "--override-keys",
        help="Regenerate keys even if they already exist.",
    ),
) -> None:
    """Generate RSA (encryption) + Ed25519 (signing) key pairs for a player identity."""
    from tractusx_testlab.security.trust.identity import PlayerIdentity

    key_dir = out_dir / label
    if not override_keys and key_dir.is_dir() and any(key_dir.iterdir()):
        identity = PlayerIdentity.load(key_dir)
        typer.echo(f"Reusing existing keys in {key_dir}/")
    else:
        identity = PlayerIdentity.generate()
        identity.save(key_dir)
        typer.echo(f"Keys saved to {key_dir}/")

    typer.echo("  encryption.pem / encryption.pub  (RSA-4096)")
    typer.echo("  signing.pem    / signing.pub     (Ed25519)")
    typer.echo(f"  Encryption fingerprint: {identity.encryption.fingerprint[:32]}...")
    typer.echo(f"  Signing    fingerprint: {identity.signing.fingerprint[:32]}...")

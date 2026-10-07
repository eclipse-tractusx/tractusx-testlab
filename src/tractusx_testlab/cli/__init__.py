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

"""Testlab CLI package — wires sub-command modules into the main Typer app."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="testlab",
    help="Tractus-X Testlab CLI — compile, encrypt, validate, and run TCKs.",
    add_completion=False,
)

# Register all commands by importing their modules (each calls @app.command())
from tractusx_testlab.cli import compile as _compile
from tractusx_testlab.cli import config as _config
from tractusx_testlab.cli import docs as _docs
from tractusx_testlab.cli import inspect as _inspect
from tractusx_testlab.cli import keys as _keys
from tractusx_testlab.cli import run as _run
from tractusx_testlab.cli import schema as _schema
from tractusx_testlab.cli import serve as _serve
from tractusx_testlab.cli import validate as _validate


def main() -> None:
    """Entry point for the ``testlab`` console script."""
    app()


if __name__ == "__main__":
    main()

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The runtime variables of ``testlab run``: a config file's, then ``--var``'s.

Split from :mod:`tractusx_testlab.cli.run` for its length.
"""

from __future__ import annotations

from pathlib import Path

import typer


def build_runtime_vars(
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

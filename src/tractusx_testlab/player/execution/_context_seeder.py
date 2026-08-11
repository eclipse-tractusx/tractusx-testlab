################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Context-seeding helpers — populate a StepContext before a TCK run begins.

Extracted from ``player.py`` to keep each module under 300 lines.  These are
pure, side-effect-free helpers that write values into a ``StepContext``; they
do not start services, open network connections, or mutate any other state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.scripting.script import Tck

logger = logging.getLogger(__name__)


def seed_context_variables(
    context: StepContext,
    tck: Tck,
    runtime_vars: Optional[dict],
) -> None:
    """Seed context with all variable sources in priority order.

    Priority (lowest → highest):
    1. Shared variables with defaults.
    2. ``env.variables`` static values (``source: value``).
    3. Operator-supplied ``runtime_vars`` (highest — overrides everything).

    Side effects: writes to *context* variables store and loads testdata files.
    """
    if tck.base_dir is not None:
        context.set_variable("_tck_root", str(tck.base_dir))
        _load_testdata(context, tck)
        _load_schemas(context, tck)

    shared_vars = getattr(tck.definition, "shared_variables", None) or {}
    if shared_vars:
        for var_name, var_def in shared_vars.items():
            if var_def.default is not None:
                context.set_variable(var_name, var_def.default)

    seed_env_variables(context, tck)

    if runtime_vars:
        for key, value in runtime_vars.items():
            context.set_variable(key, value)


def seed_env_variables(context: StepContext, tck: Tck) -> None:
    """Seed ``env.variables`` entries that carry a static ``with.value``."""
    env = getattr(tck.definition, "env", None)
    if env is None:
        return
    variables = getattr(env, "variables", None)
    if not variables or not isinstance(variables, list):
        return
    for var in variables:
        if not isinstance(var, dict):
            continue
        var_id = var.get("id")
        if not var_id:
            continue
        with_block = var.get("with") or {}
        value = with_block.get("value")
        if value is None:
            continue
        context.set_variable(var_id, value)
        returns = var.get("returns") or {}
        for field_name in returns:
            context.set_variable(f"{var_id}.{field_name}", value)


def _resolve_asset_path(base_dir: Path, folder_name: str, source: str) -> Optional[Path]:
    """Locate an asset file under *folder_name*, tolerating both package layouts.

    A compiled ``.tck`` archive stores assets under ``assets/<folder>/`` while a
    raw authoring directory keeps them in a top-level ``<folder>/``.  Both are
    valid inputs to the player, so try the compiled layout first and fall back
    to the raw one.  Returns ``None`` when the file exists in neither.
    """
    for candidate in (base_dir / "assets" / folder_name / source, base_dir / folder_name / source):
        if candidate.is_file():
            return candidate
    return None


def _load_json_assets(
    context: StepContext, tck: Any, folder_name: str, entries: Any,
) -> None:
    """Load JSON assets from *folder_name* and seed them under ``<folder>.<id>``.

    Each asset is bound to both ``<folder>.<id>`` and ``env.<folder>.<id>`` so
    that ``${{ env.<folder>.<id> }}`` and the bare ``${{ <folder>.<id> }}`` form
    both resolve.
    """
    for entry in entries:
        path = _resolve_asset_path(tck.base_dir, folder_name, entry.source)
        if path is None:
            logger.warning(
                "%s file not found, skipping: %s/%s (searched under %s)",
                folder_name.capitalize(), folder_name, entry.source, tck.base_dir,
            )
            continue
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s file %s: %s", folder_name, path, exc)
            continue
        context.set_variable(f"{folder_name}.{entry.id}", content)
        context.set_variable(f"env.{folder_name}.{entry.id}", content)
        logger.debug("Loaded %s '%s' from %s", folder_name, entry.id, path.name)


def _load_testdata(context: StepContext, tck: Any) -> None:
    """Seed context with testdata files declared in the TCK ``env.testdata`` block."""
    env_def = getattr(tck.definition, "env", None)
    _load_json_assets(context, tck, "testdata", getattr(env_def, "testdata", None) or [])


def _load_schemas(context: StepContext, tck: Any) -> None:
    """Seed context with JSON Schema files declared in the TCK ``env.schemas`` block."""
    env_def = getattr(tck.definition, "env", None)
    _load_json_assets(context, tck, "schemas", getattr(env_def, "schemas", None) or [])

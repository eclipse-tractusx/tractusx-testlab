################################################################################
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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from tractusx_testlab.models.primitives.binding_errors import MissingInputVariableError
from tractusx_testlab.models.primitives.exceptions import VariableTypeError
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.scripting.script import Tck
from tractusx_testlab.syntax import keys, variables

logger = logging.getLogger(__name__)


def seed_context_variables(
    context: StepContext,
    tck: Tck,
    runtime_vars: dict | None,
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
        declared = _declared_types(tck)
        for key, value in runtime_vars.items():
            context.set_variable(key, _as_declared_type(key, value, declared.get(key)))


def require_inputs(context: StepContext, tck: Tck) -> None:
    """Refuse a run whose TCK declares input variables the operator did not supply.

    An ``env`` variable with ``source: input`` and no default is the TCK saying
    it cannot know this value — the twin to look up, the BPN to present. That
    is a contract with the operator exactly as an infrastructure binding is,
    and it is checked in the same place and at the same time: before the first
    step, with every missing name reported at once and its description beside
    it, rather than one at a time as an empty ``${{ env.… }}`` that fails
    somewhere in the middle as a puzzling 404.
    """
    missing = {
        name: (variable.description or "")
        for name, variable in tck.required_variables().items()
        if not str(context.get_variable(name, "") or "").strip()
    }
    if missing:
        raise MissingInputVariableError(missing)


def seed_env_variables(context: StepContext, tck: Tck) -> None:
    """Seed ``env.variables`` entries that carry a static ``with.value``.

    One entry, one name. A variable used to be bound under its declared return
    key as well — ``env.usage_policy.policy`` beside ``env.usage_policy`` — so
    the same value answered to two references, only one of which the compiler
    knew about. Every variable publishes one value, so the id is the reference.
    """
    for var in _declared_variables(tck):
        value = (var.get(keys.WITH) or {}).get(keys.VALUE)
        if value is None:
            continue
        var_id = str(var[keys.ID])
        context.set_variable(var_id, _as_declared_type(var_id, value, _declared_type(var)))


def _declared_variables(tck: Tck) -> Iterator[dict]:
    """Yield every well-formed ``env.variables`` entry the TCK declares."""
    env = getattr(tck.definition, "env", None)
    entries = getattr(env, "variables", None) if env is not None else None
    if not entries or not isinstance(entries, list):
        return
    for entry in entries:
        if isinstance(entry, dict) and entry.get(keys.ID):
            yield entry


def _declared_types(tck: Tck) -> dict[str, str]:
    """Map each ``env`` variable's id to the type it publishes.

    Read for the operator's own values too — a ``--var`` override is the same
    variable the manifest declared, and a policy that arrived from a run config
    is not a different kind of thing from one written into the manifest.
    """
    types = {str(var[keys.ID]): _declared_type(var) for var in _declared_variables(tck)}
    return {name: declared for name, declared in types.items() if declared}


def _declared_type(var: dict) -> str | None:
    """Return the type a variable publishes, as its ``uses:`` verb defines it.

    The verb is the single source of truth (:mod:`tractusx_testlab.syntax.variables`):
    a ``config/connector/policy`` publishes an object whatever its ``returns:``
    block says, and a declaration that disagrees is refused at compile time
    rather than reinterpreted here. The declaration is read only when the verb
    is one the catalog does not know — which the compiler also refuses, so this
    is what a player handed an unvalidated TCK falls back to rather than a
    second opinion about a valid one.
    """
    verb = variables.verb_for(str(var.get(keys.USES) or ""))
    if verb is not None:
        return verb.type
    value_def = (var.get(keys.RETURNS) or {}).get(variables.VALUE_KEY)
    if isinstance(value_def, dict) and value_def.get(keys.TYPE):
        return str(value_def[keys.TYPE]).strip().lower()
    return None


def _as_declared_type(name: str, value: Any, declared: str | None) -> Any:
    """Read *value* as the type its variable publishes, and refuse it when it is not.

    The reading is :func:`~tractusx_testlab.syntax.variables.read_as_declared`,
    the same one the compiler runs over the manifest, so a value that gets this
    far has already been through it — this is the run reading its own seed
    rather than trusting a package it was handed, and it says the same sentence
    the compiler would have said.
    """
    parsed, problem = variables.read_as_declared(value, declared)
    if problem is not None:
        raise VariableTypeError(name, declared or "", problem)
    return parsed


def _resolve_asset_path(base_dir: Path, folder_name: str, source: str) -> Path | None:
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
    context: StepContext,
    tck: Any,
    folder_name: str,
    entries: Any,
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
                folder_name.capitalize(),
                folder_name,
                entry.source,
                tck.base_dir,
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

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Symbol-table construction for the IR builder (global env + per-test symbols)."""

from __future__ import annotations

from typing import Any

from tractusx_testlab.compiler.ir._instructions import _infer_type

# The verb-form `returns.value` block describes the variable's own type, not a
# referenceable sub-field, so it is never emitted as an `env.<id>.value` symbol.
_VALUE_RETURN_KEY = "value"

# Source tag recorded on every symbol that originates from the env.variables block.
_VARIABLES_SOURCE = "env.variables"


def build_global_symbols(
    env_raw: dict[str, Any],
) -> dict[str, Any]:
    """Build the global_symbols dict for all env-level symbols.

    Contains variables, services, schemas, and testdata.
    No `produced_by` field — globals are always available.
    """
    symbols: dict[str, Any] = {}
    _collect_variable_symbols(env_raw.get("variables", {}), symbols)
    _collect_service_symbols(env_raw.get("services", []), symbols)
    _collect_simple_symbols(env_raw.get("schemas"), "env.schemas", "object", symbols)
    _collect_simple_symbols(env_raw.get("testdata"), "env.testdata", "object", symbols)
    return symbols


def _collect_variable_symbols(
    variables: Any, symbols: dict[str, Any],
) -> None:
    """Add env.variables to the symbol table (legacy mapping or verb-form list)."""
    if isinstance(variables, list):
        _collect_verb_variable_symbols(variables, symbols)
        return
    for name, val in variables.items():
        symbols[f"env.{name}"] = {
            "source": _VARIABLES_SOURCE,
            "type": _infer_type(val),
            "default": val,
        }


def _collect_verb_variable_symbols(
    variables: list[dict[str, Any]], symbols: dict[str, Any],
) -> None:
    """Add verb-form (``id``/``uses``/``with``/``returns``) env variables.

    Each entry yields a base ``env.<id>`` symbol carrying its provided value, and
    every declared return field other than ``value`` becomes a referenceable
    ``env.<id>.<field>`` symbol. This is how complex capabilities such as
    ``config/connector/policy`` expose their artifact (e.g. ``env.<id>.policy``).
    """
    for entry in variables:
        var_id = entry.get("id", "")
        if not var_id:
            continue
        value = (entry.get("with") or {}).get("value")
        returns = entry.get("returns") or {}
        symbols[f"env.{var_id}"] = {
            "source": _VARIABLES_SOURCE,
            "type": _base_variable_type(returns, value),
            "default": value,
        }
        for field_name, field_def in returns.items():
            if field_name == _VALUE_RETURN_KEY:
                continue
            symbols[f"env.{var_id}.{field_name}"] = _build_field_entry(
                field_def, _VARIABLES_SOURCE, default_type="object",
            )


def _base_variable_type(returns: dict[str, Any], value: Any) -> str:
    """Resolve a verb variable's base type from its ``returns.value`` or value."""
    value_def = returns.get(_VALUE_RETURN_KEY)
    if isinstance(value_def, dict) and value_def.get("type"):
        return str(value_def["type"])
    return _infer_type(value)


def _collect_service_symbols(
    services: list[dict[str, Any]], symbols: dict[str, Any],
) -> None:
    """Add env.services to the symbol table."""
    for svc in services:
        svc_name = svc.get("name", "")
        returns = svc.get("returns", {})
        if returns:
            for field_name, field_def in returns.items():
                entry = _build_field_entry(field_def, "env.services", default_type="class")
                symbols[f"env.services.{svc_name}.{field_name}"] = entry
        else:
            symbols[f"env.services.{svc_name}.service"] = {
                "source": "env.services",
                "type": "class",
                "class": _service_class_from_uses(svc.get("uses", "")),
            }


def _build_field_entry(field_def: Any, source: str, default_type: str = "string") -> dict[str, Any]:
    """Build a symbol entry from a field definition."""
    entry: dict[str, Any] = {
        "source": source,
        "type": field_def.get("type", default_type) if isinstance(field_def, dict) else "string",
    }
    if isinstance(field_def, dict) and "class" in field_def:
        entry["class"] = field_def["class"]
    return entry


def _collect_simple_symbols(
    entries: Any, prefix: str, type_str: str, symbols: dict[str, Any],
) -> None:
    """Add schemas or testdata symbols to the symbol table.

    ``env.schemas`` and ``env.testdata`` are lists of ``{id, source}`` — that is
    what :class:`EnvDefinition` declares and what every TCK is written in. This
    used to iterate them as if they were a mapping, which over a list yields the
    entry dicts themselves, so the symbol names came out as their Python repr::

        "env.schemas.{'id': 'certificate_schema', 'source': '…json'}"

    ``env.schemas.certificate_schema`` was therefore absent from the symbol
    table, and anything resolving a schema through the IR found nothing.
    """
    for entry in entries or []:
        name = entry.get("id") if isinstance(entry, dict) else entry
        if not name:
            continue
        symbols[f"{prefix}.{name}"] = {
            "source": prefix,
            "type": type_str,
        }


def build_test_symbols(step_symbols: list[dict[str, Any]]) -> dict[str, Any]:
    """Build per-test symbol_table containing ONLY step/setup/teardown outputs.

    The namespace is the phase's own name, for every phase. Main-phase outputs
    used to be filed under ``steps.`` here while the runtime published them under
    ``execution.`` and every TCK — and the syntax reference, and the IDE that
    emits from it — writes ``${{ execution.<id>.<field> }}``. The runtime side of
    that mismatch was fixed; this side was not, so the compiled symbol table
    described a namespace nothing else used.
    """
    symbols: dict[str, Any] = {}

    for sym in step_symbols:
        if sym["source"] == "setup_output":
            prefix = "setup"
        elif sym["source"] == "teardown_output":
            prefix = "teardown"
        else:
            prefix = "execution"
        key = f"{prefix}.{sym['id']}.{sym['field']}"
        entry: dict[str, Any] = {
            "source": sym["source"],
            "produced_by": sym["produced_by"],
            "type": sym["type"],
        }
        if sym.get("class"):
            entry["class"] = sym["class"]
        symbols[key] = entry

    return symbols


def _service_class_from_uses(uses: str) -> str:
    """Derive a class name from a service 'uses' identifier.

    E.g. 'service/connector_service' -> 'ConnectorService'
    """
    parts = uses.rsplit("/", 1)
    raw_name = parts[-1] if parts else uses
    return "".join(word.capitalize() for word in raw_name.split("_"))

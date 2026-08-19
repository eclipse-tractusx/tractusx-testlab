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

"""Shared parsing of the LOCKED GRAMMAR v1 verb-form variable declarations.

Backward compatible: legacy flat ``name: value`` and ``{type, default}`` forms
are preserved, while the new ``uses/with/returns`` verb form is parsed
additively. Used by both the scripting builder and the player loader so the two
code paths never drift.
"""

from __future__ import annotations

from typing import Any

import tractusx_testlab.syntax.keys as keys
from tractusx_testlab.models import VariableDefinition, VariableScope, VariableSource
from tractusx_testlab.syntax.variables import verb_for

# A raw variable spec is either a scalar literal (legacy flat form) or a mapping
# (legacy ``{type, default}`` form or the new verb form).
VariableSpec = dict | str | int | float | bool | None

# A variables block is either a legacy name-keyed mapping or a list of
# ``id``-keyed verb entries.
VariablesBlock = dict | list | None

_DEFAULT_TYPE = "str"


def parse_variables_block(raw: VariablesBlock) -> dict[str, VariableDefinition]:
    """Parse a variables block (mapping or list) into VariableDefinition instances."""
    if not raw:
        return {}
    if isinstance(raw, list):
        return _parse_variable_list(raw)
    return {name: to_variable_definition(name, spec) for name, spec in raw.items()}


def _parse_variable_list(entries: list[Any]) -> dict[str, VariableDefinition]:
    """Parse a list of id-keyed verb-form entries into a name-keyed mapping."""
    result: dict[str, VariableDefinition] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"variable list entries must be mappings, got {type(entry).__name__}")
        name = entry.get(keys.ID)
        if not name:
            raise ValueError("variable list entry is missing required 'id'")
        result[str(name)] = to_variable_definition(str(name), entry)
    return result


def to_variable_definition(name: str, spec: VariableSpec) -> VariableDefinition:
    """Map one raw variable spec to a VariableDefinition (verb or legacy form)."""
    if isinstance(spec, dict):
        if keys.USES in spec:
            return _build_verb_variable(name, spec)
        return VariableDefinition(name=name, **spec)
    return VariableDefinition(name=name, default=spec)


def _build_verb_variable(name: str, spec: dict) -> VariableDefinition:
    """Build a VariableDefinition from a verb-form spec (uses/with/returns)."""
    uses = str(spec.get(keys.USES, ""))
    with_block = spec.get(keys.WITH) or {}
    value_return = (spec.get(keys.RETURNS) or {}).get(keys.VALUE) or {}

    segments = [segment for segment in uses.split("/") if segment]
    namespace = segments[0] if segments else ""
    source, generator, default, placeholder = _resolve_origin(namespace, segments, with_block)
    # The verb decides the type; what the entry declares only restates it, and
    # the compiler rejects a restatement that disagrees. The declared type is
    # still read for the forms that have no verb — the legacy name-keyed
    # mapping, and a namespace the catalog does not carry.
    verb = verb_for(uses)
    declared_type = (
        verb.type
        if verb
        else value_return.get(keys.TYPE) or _type_from_verb_path(namespace, segments)
    )

    raw_scope = with_block.get(keys.SCOPE)
    scope: VariableScope | None = VariableScope(raw_scope) if raw_scope else None

    return VariableDefinition(
        name=name,
        type=declared_type or _DEFAULT_TYPE,
        default=default,
        runtime=source is VariableSource.INPUT,
        description=spec.get(keys.DESCRIPTION),
        source=source,
        generator=generator,
        format=value_return.get(keys.FORMAT),
        placeholder=placeholder,
        scope=scope,
    )


def _type_from_verb_path(namespace: str, segments: list[str]) -> str | None:
    """Return the type token of a ``variable/type/<type>`` verb path, if present."""
    if namespace == keys.VARIABLE and len(segments) >= 3 and segments[1] == keys.TYPE:
        return segments[2]
    return None


def _resolve_origin(
    namespace: str,
    segments: list[str],
    with_block: dict,
) -> tuple[VariableSource, str | None, Any | None, str | None]:
    """Resolve (source, generator, default, placeholder) from the uses namespace.

    ``generate/<gen>`` yields a generated variable. The simple ``variable/type/<type>``
    namespace (and any complex ``config/*`` builder) is either operator-supplied at
    runtime (``with.source: input``) or carries a provided literal (``with.value``).
    """
    if namespace == keys.GENERATE:
        generator = segments[1] if len(segments) > 1 else None
        return VariableSource.GENERATED, generator, None, None
    if str(with_block.get(keys.SOURCE)) == VariableSource.INPUT.value:
        return VariableSource.INPUT, None, None, with_block.get(keys.PLACEHOLDER)
    return VariableSource.VALUE, None, with_block.get(keys.VALUE), None

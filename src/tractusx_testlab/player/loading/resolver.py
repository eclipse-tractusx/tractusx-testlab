#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""Variable and service definition resolution for ${var} and ${{ }} references."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from tractusx_testlab.syntax import patterns

from tractusx_testlab.models.authoring.definitions import ServiceDefinition

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

# ${{ expr }} pattern — matches the full double-curly wrapper
_EXPR_RE = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")
_EXPR_FULL_RE = re.compile(r"^\$\{\{\s*([^}]+?)\s*\}\}$")


def _resolve_expr(expr: str, context: "StepContext") -> object:
    """Resolve a single normalized expression against the context.

    Resolution rules:
    - ``env.X`` → context variable ``X``
    - ``execution.ID.FIELD``, ``setup.ID.FIELD``, ``teardown.ID.FIELD``,
      ``infrastructure.X.Y…`` → flat context lookup of the full dotted path
      (set by store_step_outputs or seeded by the player).
    - Anything else → flat context lookup as-is.
    """
    expr = expr.strip()
    if expr.startswith("env."):
        return context.get_variable(expr[4:])
    return context.get_variable(expr)


def resolve_str(value: str, context: "StepContext") -> object:
    """Replace ``${{ }}``, ``${var}``, and ``@var`` references in a single string.

    Priority order:
    1. ``${{ expr }}`` (double-curly) — whole-string returns raw type.
    2. ``@var`` — whole-string returns raw type.
    3. Inline ``@var`` and ``${var}`` — string interpolation.
    """
    # Whole-string expression → return raw value (preserving type)
    if "${{" in value:
        full = _EXPR_FULL_RE.match(value)
        if full:
            resolved = _resolve_expr(full.group(1), context)
            if resolved is not None:
                # If the resolved value is itself a composite (dict/list) containing
                # further ${{ }} expressions (e.g. testdata files), process them now.
                return _resolve_value(resolved, context)
            return value
        # Inline interpolation (mixed with literal text)
        value = _EXPR_RE.sub(
            lambda m: str(
                r if (r := _resolve_expr(m.group(1), context)) is not None else m.group(0)
            ),
            value,
        )

    # Whole-string @var → return raw value (preserving type)
    if value.startswith("@") and patterns.AT_VAR_REF.fullmatch(value):
        var_name = value[1:]
        resolved = context.get_variable(var_name)
        return resolved if resolved is not None else value

    # Inline @var replacements within a larger string (e.g. "@base_url/path")
    result = patterns.AT_VAR_REF.sub(
        lambda m: str(context.get_variable(m.group(1), m.group(0))),
        value,
    )

    # Also handle ${var} references
    result = patterns.VAR_REF.sub(
        lambda m: str(context.get_variable(m.group(1), m.group(0))),
        result,
    )
    return result


def _resolve_value(value: object, context: "StepContext") -> object:
    """Recursively resolve variable references in any value type."""
    if isinstance(value, str):
        return resolve_str(value, context)
    if isinstance(value, dict):
        return resolve_params(value, context)
    if isinstance(value, list):
        return [_resolve_value(item, context) for item in value]
    return value


def resolve_params(params: dict, context: "StepContext") -> dict:
    """Replace ``${var}`` and ``@var`` references in param values with context variables."""
    resolved: dict[str, object] = {}
    for key, value in params.items():
        resolved[key] = _resolve_value(value, context)
    return resolved


def resolve_service_def(svc_def: ServiceDefinition, context: "StepContext") -> ServiceDefinition:
    """Return a copy of *svc_def* with ``${var}`` and ``@var`` references resolved."""
    resolved_base_url = resolve_str(svc_def.base_url, context)
    if isinstance(resolved_base_url, str):
        base_url = resolved_base_url
    else:
        base_url = str(resolved_base_url)
    resolved_auth = {
        auth_key: resolve_str(auth_value, context) if isinstance(auth_value, str) else auth_value
        for auth_key, auth_value in svc_def.auth.items()
    }
    resolved_params: dict | None = None
    if svc_def.params:
        resolved_params = {
            param_key: resolve_str(param_value, context) if isinstance(param_value, str) else param_value
            for param_key, param_value in svc_def.params.items()
        }
    return ServiceDefinition(
        name=svc_def.name,
        type=svc_def.type,
        base_url=base_url,
        auth=resolved_auth,
        params=resolved_params,
    )

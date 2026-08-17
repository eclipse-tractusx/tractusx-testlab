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

"""Resolving ``${{ ... }}`` references in a step's parameters.

``${{ ... }}`` is the only reference syntax (ADR-0010).  Two older spellings —
``${var}`` and ``@var`` — were resolved here as well, which meant the same value
could be written three ways and the compiler only understood one of them.  They
are gone; the compiler rejects them by name so a script written against the old
grammar gets an error that says what to write instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models import UnresolvedReferenceError
from tractusx_testlab.syntax import patterns

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


#: Distinguishes "no such variable" from "a variable whose value is None".
#: ``get_variable`` returns ``None`` for both, and conflating them is what let an
#: undefined reference look like an ordinary empty value.
_MISSING = object()


def _lookup(expr: str, context: StepContext) -> object:
    """Return what *expr* names, or :data:`_MISSING` if it names nothing.

    Resolution rules:
    - ``env.X`` → context variable ``X``
    - ``execution.ID.FIELD``, ``setup.ID.FIELD``, ``teardown.ID.FIELD``,
      ``infrastructure.X.Y…`` → flat context lookup of the full dotted path
      (set by store_step_outputs or seeded by the player).
    - Anything else → flat context lookup as-is.
    """
    name = expr[4:] if expr.startswith("env.") else expr
    if context.has_variable(name):
        return context.get_variable(name)
    return _MISSING


def _require(expr: str, context: StepContext) -> object:
    """Resolve *expr*, or refuse the run.

    A reference that resolved to nothing used to be replaced by its own template
    text and handed to the step as data: a URL built from an undefined variable
    was requested verbatim, and a BPN compared against one compared as a string
    containing braces. Neither failed, and both produced a verdict about a system
    that was never asked the question.
    """
    value = _lookup(expr, context)
    if value is _MISSING:
        raise UnresolvedReferenceError(expr, list(context.variables))
    return value


def resolve_str(value: str, context: StepContext) -> object:
    """Replace ``${{ ... }}`` references in a single string.

    A reference that is the whole string returns the raw value, so a dict or a
    list survives as itself rather than being stringified.  Mixed with literal
    text, it interpolates.

    Raises:
        UnresolvedReferenceError: if any reference names nothing in scope.
    """
    if "${{" not in value:
        return value

    full = patterns.EXPR_REF_FULL.match(value)
    if full:
        # A resolved composite may itself carry references — testdata files
        # routinely do — so it is walked before being handed back.
        return _resolve_value(_require(full.group(1), context), context)

    return patterns.EXPR_REF.sub(
        lambda m: str(_require(m.group(1), context)),
        value,
    )


def _resolve_value(value: object, context: StepContext) -> object:
    """Recursively resolve variable references in any value type."""
    if isinstance(value, str):
        return resolve_str(value, context)
    if isinstance(value, dict):
        return resolve_params(value, context)
    if isinstance(value, list):
        return [_resolve_value(item, context) for item in value]
    return value


def resolve_params(params: dict, context: StepContext) -> dict:
    """Resolve every ``${{ ... }}`` reference in a step's ``with:`` block."""
    resolved: dict[str, object] = {}
    for key, value in params.items():
        resolved[key] = _resolve_value(value, context)
    return resolved



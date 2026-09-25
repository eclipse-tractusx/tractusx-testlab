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

"""Resolving ``${{ ... }}`` references in a step's parameters.

``${{ ... }}`` is the only reference syntax (ADR-0010).  Two older spellings —
``${var}`` and ``@var`` — were resolved here as well, which meant the same value
could be written three ways and the compiler only understood one of them.  They
are gone; the compiler rejects them by name so a test written against the old
grammar gets an error that says what to write instead.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING

from tractusx_testlab.models import UnresolvedReferenceError
from tractusx_testlab.models.primitives.exceptions import AuthoringError, TestLabError
from tractusx_testlab.syntax import patterns

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


#: Distinguishes "no such variable" from "a variable whose value is None".
#: ``get_variable`` returns ``None`` for both, and conflating them is what let an
#: undefined reference look like an ordinary empty value.
_MISSING = object()

#: How deep TCK-authored content may nest references into more TCK-authored
#: content. Test data that names test data is ordinary; a cycle is not, and
#: used to end the run with a ``RecursionError`` no step could report.
MAX_TEMPLATE_DEPTH = 16


class TemplateDepthError(AuthoringError):
    """Raised when TCK-authored content references itself, directly or through others."""

    def __init__(self, reference: str) -> None:
        self.reference = reference
        super().__init__(
            f"'${{{{ {reference} }}}}' nests references more than {MAX_TEMPLATE_DEPTH} deep — "
            "test data or an env value that names itself, directly or through another."
        )


def _name_of(expr: str) -> str:
    """The context variable *expr* reads.

    Resolution rules:
    - ``env.X`` → context variable ``X``
    - ``execution.ID.FIELD``, ``setup.ID.FIELD``, ``teardown.ID.FIELD``,
      ``infrastructure.X.Y…`` → flat context lookup of the full dotted path
      (set by store_step_outputs or seeded by the player).
    - Anything else → flat context lookup as-is.
    """
    return expr[4:] if expr.startswith("env.") else expr


def _require(expr: str, context: StepContext) -> tuple[str, object]:
    """Resolve *expr* to the variable it names and that variable's value, or refuse the run.

    A reference that resolved to nothing used to be replaced by its own template
    text and handed to the step as data: a URL built from an undefined variable
    was requested verbatim, and a BPN compared against one compared as a string
    containing braces. Neither failed, and both produced a verdict about a system
    that was never asked the question.
    """
    name = _name_of(expr)
    if not context.has_variable(name):
        raise UnresolvedReferenceError(expr, list(context.variables))
    return name, context.get_variable(name)


def resolve_str(value: str, context: StepContext, _depth: int = 0) -> object:
    """Replace ``${{ ... }}`` references in a single string.

    A reference that is the whole string returns the raw value, so a dict or a
    list survives as itself rather than being stringified.  Mixed with literal
    text, it interpolates.

    What a reference resolves to is resolved again only when it is part of the
    test — test data or a static ``env`` value (``StepContext.is_template``),
    whose references the author wrote. Anything the run learned while running
    is data and is handed over as it is: a step output carries what a remote
    service answered, and re-reading a ``${{ ... }}`` in it let that service
    choose what the next step is given — the operator's connector API key
    expanded into a URL it controls.

    Raises:
        UnresolvedReferenceError: if any reference names nothing in scope.
        TemplateDepthError: if authored content nests references into itself.
    """
    if "${{" not in value:
        return value

    full = patterns.EXPR_REF_FULL.match(value)
    if full:
        name, resolved = _require(full.group(1), context)
        if not context.is_template(name):
            return resolved
        if _depth >= MAX_TEMPLATE_DEPTH:
            raise TemplateDepthError(full.group(1))
        return _resolve_value(resolved, context, _depth + 1)

    # Interpolated text is not rescanned: `re.sub` does not read its own
    # replacements, so whatever a reference stands for is inserted as it is.
    return patterns.EXPR_REF.sub(
        lambda m: str(_require(m.group(1), context)[1]),
        value,
    )


def _resolve_value(value: object, context: StepContext, _depth: int = 0) -> object:
    """Recursively resolve variable references in any value type."""
    if isinstance(value, str):
        return resolve_str(value, context, _depth)
    if isinstance(value, dict):
        return {key: _resolve_value(item, context, _depth) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, context, _depth) for item in value]
    return value


def resolve_params(params: dict, context: StepContext, deferred: Collection[str] = ()) -> dict:
    """Resolve every ``${{ ... }}`` reference in a step's ``with:`` block.

    A key in *deferred* is handed over as written. That is how a flow step
    receives the steps nested inside it: each nested step resolves its own
    ``with:`` when it runs, so it reads what the steps before it published —
    and, inside ``flow/for_each``, the item it is running for, which does not
    exist yet when the flow step itself starts.
    """
    return {
        key: value if key in deferred else _resolve_value(value, context)
        for key, value in params.items()
    }


def try_resolve_params(
    params: dict, context: StepContext, deferred: Collection[str] = ()
) -> dict | None:
    """Resolve a ``with:`` block, or answer ``None`` rather than raise.

    For the callers that resolve a block *before* running the step — the phase
    runner, which publishes what the step is about to be given — and for which a
    reference naming nothing is not their failure to report. They hand the
    unresolved block on, and the step runner raises the same error where it can
    be turned into a failed step.
    """
    try:
        return resolve_params(params, context, deferred)
    except TestLabError:
        return None

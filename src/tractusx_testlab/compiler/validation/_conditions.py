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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""Holding every step's ``if:`` to an expression the run will evaluate as written.

``if:`` was carried into the compiled test as the author wrote it and read
only when its step was about to run. An expression the evaluator did not
recognise ran the step; a variable it did not find read as empty, so the
comparison came out false and the step was skipped; an ``if:`` in teardown or
on a nested step was never read at all. Each time the run did something other
than what the test said, and ``testlab compile`` answered OK.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.compiler.validation._variable_references import nested_steps
from tractusx_testlab.models import StepDefinition, TestDefinition
from tractusx_testlab.steps._condition_parsing import OUTCOMES, Condition, parse_condition
from tractusx_testlab.syntax import keys

#: The phases whose steps publish outputs a later step's ``vars.`` can read.
_PHASES = ("setup", "execution", "teardown")

_GRAMMAR = (
    "An 'if:' is one of: success(), failure(), always(), "
    "steps.<id>.outcome == 'success' | 'failure' | 'skipped' (or !=), "
    "vars.<name>, or vars.<name> == '<value>' (or !=), optionally inside '${{ }}'. "
    "There is no 'and', 'or' or 'not': a flow/if step with 'match: all' or "
    "'match: any' combines conditions."
)

_TEARDOWN = (
    "Teardown runs every step whatever happened before it, and never reads 'if:'. "
    "Remove it, or move the step to execution."
)

_NESTED = (
    "A step nested in a flow step never reads its 'if:'. Put the condition on a "
    "flow/if step around it instead."
)


@dataclass(slots=True)
class _Published:
    """What the steps checked so far have made readable to a later ``if:``."""

    #: ``<phase>.<id>`` of every step, nested ones included, mapped to the
    #: names it lists under ``returns:`` — the only outputs the run publishes.
    returns: dict[str, frozenset[str]] = field(default_factory=dict)
    #: The same names unqualified: the run also publishes each one bare.
    bare: set[str] = field(default_factory=set)

    def add(self, phase: str, step_id: str | None, returns: object) -> None:
        names = frozenset(str(name) for name in returns) if isinstance(returns, dict) else None
        if step_id:
            self.returns[f"{phase}.{step_id}"] = names or frozenset()
        self.bare.update(names or ())


def condition_findings(
    test: TestDefinition, scope: frozenset[str] | None
) -> Iterator[tuple[str, int, str, str]]:
    """Every ``(phase, step index, field, message)`` for an ``if:`` the run would misread.

    *scope* is what :func:`~tractusx_testlab.compiler.validation.validator._scope_of`
    assembles. Without it — a test validated with no manifest around it — a
    bare ``vars.<name>`` is not checked, because the manifest's variables are
    exactly the names that cannot be seen.
    """
    published = _Published()
    for phase in _PHASES:
        earlier: set[str] = set()
        for idx, step in enumerate(getattr(test, phase)):
            step_cls = StepRegistry.get_any(step.uses)
            nested = list(nested_steps(step_cls, step.with_))
            for where, nested_step in nested:
                if keys.IF in nested_step:
                    yield phase, idx, f"{where}.{keys.IF}", _NESTED
            problem = _step_problem(step, phase, earlier, published, scope)
            if problem:
                yield phase, idx, keys.IF, problem
            published.add(phase, step.id, step.returns)
            for _, nested_step in nested:
                nested_id = nested_step.get(keys.ID)
                published.add(
                    phase, str(nested_id) if nested_id else None, nested_step.get(keys.RETURNS)
                )
            if step.id:
                earlier.add(step.id)


def _step_problem(
    step: StepDefinition,
    phase: str,
    earlier: set[str],
    published: _Published,
    scope: frozenset[str] | None,
) -> str | None:
    condition = step.if_condition
    if condition is None:
        return None
    if phase == "teardown":
        return _TEARDOWN
    parsed = parse_condition(condition)
    if parsed is None:
        return f"'{condition}' is not an expression testlab evaluates. {_GRAMMAR}"
    if parsed.legacy:
        return (
            f"'{condition}' uses the retired '${{name}}' spelling. "
            f"Write '${{{{ vars.{parsed.name} }}}}'."
        )
    if parsed.kind == "outcome":
        return _outcome_problem(parsed, phase, earlier)
    if parsed.kind in ("compare", "truthy"):
        return _variable_problem(parsed.name, published, scope)
    return None


def _outcome_problem(parsed: Condition, phase: str, earlier: set[str]) -> str | None:
    if parsed.expected not in OUTCOMES:
        return (
            f"'steps.{parsed.name}.outcome' is compared with '{parsed.expected}', which no "
            f"step's outcome ever is: it is 'success', 'failure' or 'skipped'."
        )
    if parsed.name not in earlier:
        return (
            f"'steps.{parsed.name}' names no step before this one in {phase}. An outcome "
            f"is read from the steps this phase has already run, by their 'id'."
        )
    return None


def _variable_problem(name: str, published: _Published, scope: frozenset[str] | None) -> str | None:
    parts = name.split(".")
    if parts[0] in _PHASES and len(parts) > 2:
        step_ref, output = ".".join(parts[:2]), ".".join(parts[2:])
        returns = published.returns.get(step_ref)
        if returns is None:
            return (
                f"'vars.{name}' reads '{step_ref}', which is no step that runs before this "
                f"one. A condition reads what an earlier step returned."
            )
        if output not in returns:
            listed = ", ".join(sorted(returns)) or "nothing"
            return (
                f"'vars.{name}' reads '{output}', which '{step_ref}' does not list under "
                f"'returns:' (it returns: {listed}). Only a declared return is published."
            )
        return None
    if len(parts) == 2 and name in published.returns:
        return (
            f"'vars.{name}' names a step, not a value. Name the field it returned: "
            f"'vars.{name}.<field>'."
        )
    # `env.<id>` is how a reference names a manifest variable, not how the run
    # holds it; `env.testdata.<id>` and `env.schemas.<id>` are held as written.
    env_variable = parts[0] == "env" and len(parts) == 2
    if scope is None or name in published.bare or f"env.{name}" in scope:
        return None
    if name in scope and not env_variable:
        return None
    hint = f" A manifest variable is read by its id: 'vars.{parts[1]}'." if env_variable else ""
    return (
        f"'vars.{name}' names nothing this run holds when the step starts. A condition "
        f"reads a manifest variable ('vars.<id>'), a binding, or what an earlier step "
        f"returned ('vars.<phase>.<step id>.<field>').{hint}"
    )

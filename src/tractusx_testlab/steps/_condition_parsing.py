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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""Condition expression grammar — one parser, read by the compiler and the player.

:func:`parse_condition` is the whole grammar. The compiler refuses an ``if:``
it returns ``None`` for, and the player evaluates what it returns, so the two
cannot disagree about what an expression means. They used to share only the
regexes, and only the player ever called them: an expression nothing matched
compiled cleanly and then ran its step unconditionally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from tractusx_testlab.models.primitives.enums import StepStatus

if TYPE_CHECKING:
    from tractusx_testlab.models.runtime.results import StepResult
    from tractusx_testlab.player.execution.context import StepContext

# ---------------------------------------------------------------------------
# Regex patterns for parsing condition expressions
# ---------------------------------------------------------------------------

# Status functions: success(), failure(), always()
STATUS_FN_RE = re.compile(r"^(success|failure|always)\(\)$")

# Step outcome: steps.<name>.outcome == 'value'
STEP_OUTCOME_RE = re.compile(r"^steps\.([^\s.]+)\.outcome\s*(==|!=)\s*'([^']*)'$")

# Variable comparison: vars.<name> == 'value' (quoted) or vars.<name> == value (unquoted)
VARS_COMPARISON_RE = re.compile(r"^vars\.([^\s=!]+)\s*(==|!=)\s*(?:'([^']*)'|(\S+))$")

# Variable truthy: vars.<name>
VARS_TRUTHY_RE = re.compile(r"^vars\.([^\s]+)$")

# Legacy ${var} comparison (backward compat)
LEGACY_COMPARISON_RE = re.compile(r"^\$\{([^}]+)\}\s*(==|!=)\s*(?:'([^']*)'|(\S+))$")

# Legacy ${var} truthy (backward compat)
LEGACY_TRUTHY_RE = re.compile(r"^\$\{([^}]+)\}$")

#: The step id the phase runner writes into a result's name: ``t[fetch]:http/get``
#: in execution, ``t[setup:fetch]:http/get`` in the other phases.
_STEP_ID_IN_NAME_RE = re.compile(r"\[(?:[a-z]+:)?([^\[\]:]+)\]:[^\[\]]*$")

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Condition:
    """One ``if:`` expression, parsed.

    *name* is the status function, the step id or the variable name the
    expression reads; *operator* and *expected* are empty for a status function
    and a truthy check. *legacy* marks the retired ``${name}`` spelling, which
    the player still reads and the compiler no longer accepts.
    """

    kind: Literal["status", "outcome", "compare", "truthy"]
    name: str
    operator: str = ""
    expected: str = ""
    legacy: bool = False


def unwrap(condition: str) -> str:
    """*condition* without its padding and optional ``${{ }}`` wrapper."""
    expr = condition.strip()
    # String ops rather than a regex: no backtracking on an author's input.
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2].strip()
    return expr


def parse_condition(condition: str) -> Condition | None:
    """What *condition* reads and compares, or ``None`` when it is not the grammar.

    An empty expression is ``success()``, the default a step without ``if:`` has.
    """
    expr = unwrap(condition)
    if not expr:
        return Condition("status", "success")

    if m := STATUS_FN_RE.match(expr):
        return Condition("status", m.group(1))
    if m := STEP_OUTCOME_RE.match(expr):
        return Condition("outcome", m.group(1), m.group(2), m.group(3))
    for comparison, truthy, legacy in (
        (VARS_COMPARISON_RE, VARS_TRUTHY_RE, False),
        (LEGACY_COMPARISON_RE, LEGACY_TRUTHY_RE, True),
    ):
        if m := comparison.match(expr):
            expected = m.group(3) if m.group(3) is not None else m.group(4)
            return Condition("compare", m.group(1), m.group(2), expected, legacy)
        if m := truthy.match(expr):
            return Condition("truthy", m.group(1), legacy=legacy)
    return None


# ---------------------------------------------------------------------------
# Outcome mapping
# ---------------------------------------------------------------------------

OUTCOME_MAP = {
    StepStatus.PASSED: "success",
    StepStatus.FAILED: "failure",
    StepStatus.SKIPPED: "skipped",
}

#: Every value ``steps.<id>.outcome`` can have; a comparison with anything else
#: has the same answer on every run.
OUTCOMES = frozenset(OUTCOME_MAP.values())

# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------


def evaluate_status_fn(fn_name: str, previous_results: list[StepResult]) -> bool:
    """Evaluate a status function against previous step results."""
    if fn_name == "always":
        return True

    has_failure = any(r.status == StepStatus.FAILED for r in previous_results)

    if fn_name == "failure":
        return has_failure
    # success — true only when no previous step failed
    return not has_failure


def evaluate_step_outcome(
    step_name: str,
    operator: str,
    expected: str,
    previous_results: list[StepResult],
) -> bool:
    """Evaluate ``steps.<name>.outcome == 'success'``."""
    result = find_step_result(step_name, previous_results)

    if result is None:
        actual_outcome = "skipped"
    else:
        actual_outcome = OUTCOME_MAP.get(result.status, str(result.status.value).lower())

    if operator == "==":
        return actual_outcome == expected
    return actual_outcome != expected


def find_step_result(step_id: str, results: list[StepResult]) -> StepResult | None:
    """The latest result of the step whose id is *step_id*.

    Matched on the id alone, as the phase runner writes it into the result's
    name. A substring used to be enough, so ``steps.fetch.outcome`` could read
    the outcome of ``fetch_again``.
    """
    for r in reversed(results):
        m = _STEP_ID_IN_NAME_RE.search(r.step_name)
        if m and m.group(1) == step_id:
            return r
    return None


def evaluate_comparison(
    var_name: str,
    operator: str,
    expected: str,
    context: StepContext,
) -> bool:
    """Evaluate ``vars.<name> == 'value'`` or ``vars.<name> != 'value'``."""
    actual = context.get_variable(var_name)
    actual_str = _to_comparable(actual)

    if operator == "==":
        return actual_str == expected
    return actual_str != expected


def evaluate_truthy(var_name: str, context: StepContext) -> bool:
    """Return ``True`` when the variable exists and is truthy."""
    value = context.get_variable(var_name)
    return bool(value)


def _to_comparable(value: Any) -> str:
    """Coerce a runtime value to a string for comparison.

    Booleans are lowercased (``true``/``false``) to match YAML conventions.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)

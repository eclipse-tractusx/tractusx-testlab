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

"""Condition expression grammar — compiled regexes and evaluation helpers.

This module single-sources the expression grammar used by both compile-time
validation and runtime evaluation of ``if`` conditions on step definitions.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

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
STEP_OUTCOME_RE = re.compile(
    r"^steps\.([^\s.]+)\.outcome\s*(==|!=)\s*'([^']*)'$"
)

# Variable comparison: vars.<name> == 'value' (quoted) or vars.<name> == value (unquoted)
VARS_COMPARISON_RE = re.compile(
    r"^vars\.([^\s=!]+)\s*(==|!=)\s*(?:'([^']*)'|(\S+))$"
)

# Variable truthy: vars.<name>
VARS_TRUTHY_RE = re.compile(r"^vars\.([^\s]+)$")

# Legacy ${var} comparison (backward compat)
LEGACY_COMPARISON_RE = re.compile(
    r"^\$\{([^}]+)\}\s*(==|!=)\s*(?:'([^']*)'|(\S+))$"
)

# Legacy ${var} truthy (backward compat)
LEGACY_TRUTHY_RE = re.compile(r"^\$\{([^}]+)\}$")

# ---------------------------------------------------------------------------
# Outcome mapping
# ---------------------------------------------------------------------------

OUTCOME_MAP = {
    StepStatus.PASSED: "success",
    StepStatus.FAILED: "failure",
    StepStatus.SKIPPED: "skipped",
}

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


def find_step_result(name: str, results: list[StepResult]) -> StepResult | None:
    """Find a step result by name (exact or suffix match)."""
    for r in reversed(results):
        if r.step_name == name:
            return r
        parts = r.step_name.rsplit(":", 1)
        if len(parts) == 2 and parts[1] == name:
            return r
    for r in reversed(results):
        if name in r.step_name:
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

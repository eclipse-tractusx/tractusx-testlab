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

"""Evaluates ``if`` conditions on step definitions.

Condition expressions follow a syntax inspired by GitHub Actions:

Expressions are wrapped in ``${{ }}`` (the wrapper is optional for
backward compatibility).

Status functions
    ``${{ success() }}``   — true when all previous steps passed (default).
    ``${{ failure() }}``   — true when at least one previous step failed.
    ``${{ always() }}``    — always true; the step runs regardless of status.

Step outcome references
    ``${{ steps.<name>.outcome == 'success' }}``
    ``${{ steps.<name>.outcome == 'failure' }}``
    ``${{ steps.<name>.outcome == 'skipped' }}``

Variable comparisons
    ``${{ vars.<name> == 'value' }}``   — equals.
    ``${{ vars.<name> != 'value' }}``   — not equals.

Truthy check
    ``${{ vars.<name> }}``              — true when the variable is truthy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.steps._condition_parsing import (
    LEGACY_COMPARISON_RE,
    LEGACY_TRUTHY_RE,
    STATUS_FN_RE,
    STEP_OUTCOME_RE,
    VARS_COMPARISON_RE,
    VARS_TRUTHY_RE,
    evaluate_comparison,
    evaluate_status_fn,
    evaluate_step_outcome,
    evaluate_truthy,
)

if TYPE_CHECKING:
    from tractusx_testlab.models.runtime.results import StepResult
    from tractusx_testlab.player.execution.context import StepContext


class ConditionEvaluator:
    """Evaluates ``if`` condition strings against runtime state."""

    @staticmethod
    def should_run(
        condition: str | None,
        previous_results: list[StepResult],
        context: StepContext,
    ) -> bool:
        """Return ``True`` if the step should execute.

        Args:
            condition: The raw ``if`` expression string, or ``None`` (always run).
            previous_results: Results of all steps executed so far in the script.
            context: The current execution context (for variable lookups).

        Returns:
            ``True`` if the condition is met (step should run),
            ``False`` if the step should be skipped.
        """
        if condition is None:
            return True

        expr = condition.strip()
        if not expr:
            return True

        # Strip ${{ }} wrapper if present (string ops — no regex backtracking)
        if expr.startswith("${{") and expr.endswith("}}"):
            expr = expr[3:-2].strip()

        if not expr:
            return True

        # --- Status functions: success(), failure(), always() ----------------
        m = STATUS_FN_RE.match(expr)
        if m:
            return evaluate_status_fn(m.group(1), previous_results)

        # --- Step outcome: steps.<name>.outcome == 'value' -------------------
        m = STEP_OUTCOME_RE.match(expr)
        if m:
            step_name = m.group(1)
            operator = m.group(2)
            expected = m.group(3)
            return evaluate_step_outcome(step_name, operator, expected, previous_results)

        # --- Variable comparison: vars.<name> == 'value' ---------------------
        m = VARS_COMPARISON_RE.match(expr)
        if m:
            var_name = m.group(1)
            operator = m.group(2)
            expected = m.group(3) if m.group(3) is not None else m.group(4)
            return evaluate_comparison(var_name, operator, expected, context)

        # --- Variable truthy: vars.<name> ------------------------------------
        m = VARS_TRUTHY_RE.match(expr)
        if m:
            return evaluate_truthy(m.group(1), context)

        # --- Legacy: ${var} == 'value' (backward compat) ---------------------
        m = LEGACY_COMPARISON_RE.match(expr)
        if m:
            var_name = m.group(1)
            operator = m.group(2)
            expected = m.group(3) if m.group(3) is not None else m.group(4)
            return evaluate_comparison(var_name, operator, expected, context)

        # --- Legacy: ${var} (backward compat) --------------------------------
        m = LEGACY_TRUTHY_RE.match(expr)
        if m:
            return evaluate_truthy(m.group(1), context)

        # Unrecognised expression → do not skip (safe default)
        return True


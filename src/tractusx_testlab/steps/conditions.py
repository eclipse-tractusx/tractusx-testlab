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

"""Evaluates ``if`` conditions on step definitions.

Condition expressions follow a syntax inspired by GitHub Actions:

Expressions are wrapped in ``${{ }}`` (the wrapper is optional for
backward compatibility).

Status functions
    ``${{ success() }}``   — true when all previous steps passed (default).
    ``${{ failure() }}``   — true when at least one previous step failed.
    ``${{ always() }}``    — always true; the step runs regardless of status.

Step outcome references
    ``${{ steps.<id>.outcome == 'success' }}``
    ``${{ steps.<id>.outcome == 'failure' }}``
    ``${{ steps.<id>.outcome == 'skipped' }}``

Variable comparisons
    ``${{ vars.<name> == 'value' }}``   — equals.
    ``${{ vars.<name> != 'value' }}``   — not equals.

Truthy check
    ``${{ vars.<name> }}``              — true when the variable is truthy.

A step's outputs are variables too: ``vars.<phase>.<id>.<field>`` reads the
``<field>`` an earlier step listed under ``returns:``.

The grammar is :func:`~tractusx_testlab.steps._condition_parsing.parse_condition`;
the compiler refuses an expression outside it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.steps._condition_parsing import (
    evaluate_comparison,
    evaluate_status_fn,
    evaluate_step_outcome,
    evaluate_truthy,
    parse_condition,
)

if TYPE_CHECKING:
    from tractusx_testlab.models.runtime.results import StepResult
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


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
            previous_results: Results of the steps this phase has run so far.
            context: The current execution context (for variable lookups).

        Returns:
            ``True`` if the condition is met (step should run),
            ``False`` if the step should be skipped.
        """
        if condition is None:
            return True

        parsed = parse_condition(condition)
        if parsed is None:
            # Only a package compiled before the compiler checked `if:` gets
            # here. Running the step is what such a package has always done;
            # the warning is so that it no longer does it unnoticed.
            logger.warning("Unrecognised if: condition %r; running the step.", condition)
            return True

        if parsed.kind == "status":
            return evaluate_status_fn(parsed.name, previous_results)
        if parsed.kind == "outcome":
            return evaluate_step_outcome(
                parsed.name, parsed.operator, parsed.expected, previous_results
            )
        if parsed.kind == "compare":
            return evaluate_comparison(parsed.name, parsed.operator, parsed.expected, context)
        return evaluate_truthy(parsed.name, context)

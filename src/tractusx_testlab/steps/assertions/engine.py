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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""Evaluates a step's ``validate:`` block against the output the step produced."""

from __future__ import annotations

from tractusx_testlab.models import (
    AssertionResult,
    AssertionSeverity,
    AssertionSummary,
    StepResult,
)
from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.steps._checks import check_schema_validation
from tractusx_testlab.steps._checks.extraction import extract_path
from tractusx_testlab.steps.assertions.operators import RANGE_OPERATORS, apply_operator
from tractusx_testlab.steps.assertions.vocabulary import (
    AssertionKind,
    ResolvedAssertion,
    resolve,
)


class AssertionEngine:
    """Evaluates a list of assertions against a step's output value."""

    @staticmethod
    def evaluate(assertions: list[Assertion], output: object) -> list[AssertionResult]:
        """Evaluate every ``validate:`` entry against the output the step produced."""
        return [AssertionEngine._evaluate_one(assertion, output) for assertion in assertions]

    @staticmethod
    def _evaluate_one(assertion: Assertion, output: object) -> AssertionResult:
        params = assertion.with_ or {}
        severity = AssertionSeverity(params.get("severity", "HARD"))
        resolved = resolve(assertion.uses, params)

        # An assertion that cannot be understood is reported as a failure that
        # names the problem. Guessing at what was meant is how a broken check
        # ends up looking like a passing one.
        if isinstance(resolved, str):
            return AssertionResult(
                assertion=assertion,
                passed=False,
                expected=None,
                actual=None,
                message=resolved,
                severity=severity,
            )

        actual = AssertionEngine._extract_subject(output, params, resolved)
        expected = AssertionEngine._resolve_expected(params, resolved)
        passed, message = AssertionEngine._check(resolved, actual, expected)

        return AssertionResult(
            assertion=assertion,
            passed=passed,
            expected=expected,
            actual=actual,
            message="" if passed else message,
            severity=severity,
        )

    @staticmethod
    def _extract_subject(output: object, params: dict, resolved: ResolvedAssertion) -> object:
        """Find the value the assertion is about.

        ``input`` names one of the step's declared returns; ``validate/field``
        then descends ``path`` inside it, which is what makes the block's two
        fields — pick an output, name a field within it — mean what they say.
        """
        subject = extract_path(output, params.get("input"))
        if resolved.kind is AssertionKind.FIELD:
            path = params.get("path")
            if path:
                subject = extract_path(subject, path)
        return subject

    @staticmethod
    def _resolve_expected(params: dict, resolved: ResolvedAssertion) -> object:
        """Read what the assertion compares against.

        No dereferencing happens here.  A ``validate:`` block's ``with:`` is
        resolved by the same ``${{ ... }}`` pass every other step parameter goes
        through, before the engine ever sees it — so by this point ``value`` is
        already the value.  Two further spellings used to be honoured at this
        point alone, ``@name`` and ``source: VARIABLE``, which meant an assertion
        could name a variable three ways and the compiler validated one of them.
        """
        if resolved.kind is AssertionKind.SCHEMA:
            return params.get("schema")
        if resolved.operator in RANGE_OPERATORS:
            return [params.get("min"), params.get("max")]
        return params.get("value")

    @staticmethod
    def _check(resolved: ResolvedAssertion, actual: object, expected: object) -> tuple[bool, str]:
        """Run the resolved check over the extracted value."""
        if resolved.kind is AssertionKind.SCHEMA:
            return check_schema_validation(actual, expected, None)
        return apply_operator(str(resolved.operator), actual, expected)

    @staticmethod
    def extract_path(
        output: object, path: str | None, declared: frozenset[str] | None = None
    ) -> object:
        """Extract a value from a nested dict/list/object using dot-separated *path*.

        *declared* restricts which first segments resolve — see
        :func:`~tractusx_testlab.steps._checks.extraction.extract_path`.
        """
        return extract_path(output, path, declared)

    @staticmethod
    def has_hard_failure(results: list[AssertionResult]) -> bool:
        return any(
            not result.passed and result.severity == AssertionSeverity.HARD for result in results
        )

    @staticmethod
    def build_summary(
        step_results: list[StepResult], declared: int | None = None
    ) -> AssertionSummary:
        """Aggregate assertion counts across step results.

        *declared* is how many checks the executed steps asked for. Passing it
        lets the summary report the difference between "nothing was declared"
        and "something was declared and did not run" — see
        :attr:`AssertionSummary.unevaluated`.
        """
        total = passed = failed_hard = failed_soft = 0
        for step_result in step_results:
            for assertion_result in step_result.assertions:
                total += 1
                if assertion_result.passed:
                    passed += 1
                elif assertion_result.severity == AssertionSeverity.HARD:
                    failed_hard += 1
                else:
                    failed_soft += 1
        return AssertionSummary(
            declared=total if declared is None else declared,
            total=total,
            passed=passed,
            failed_hard=failed_hard,
            failed_soft=failed_soft,
        )

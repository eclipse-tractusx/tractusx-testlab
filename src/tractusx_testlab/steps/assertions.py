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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Evaluates assertion blocks against step outputs."""

from __future__ import annotations

from typing import Optional

from tractusx_testlab.models import (
    AssertionResult,
    AssertionSeverity,
    AssertionSummary,
    StepResult,
    ValueSource,
)
from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.models.primitives.enums import AssertionType
from tractusx_testlab.steps import _checks
from tractusx_testlab.steps._checks.extraction import (
    extract_path,
    _traverse_dict,
    _dict_get,
    _snake_to_camel,
    _match_predicate_value,
    _find_by_predicate,
    _PREDICATE_RE,
    _SENTINEL,
)


# Maps assertion ``uses`` identifiers to ``AssertionType`` enum values.
_USES_TO_TYPE: dict[str, AssertionType] = {
    "assert/not_null": AssertionType.NOT_NULL,
    "assert/not_empty": AssertionType.NOT_EMPTY,
    "assert/equals": AssertionType.EQUALS,
    "assert/not_equals": AssertionType.NOT_EQUALS,
    "assert/contains": AssertionType.CONTAINS,
    "assert/not_contains": AssertionType.NOT_CONTAINS,
    "assert/schema": AssertionType.SCHEMA,
    "assert/schema_validation": AssertionType.SCHEMA_VALIDATION,
    "assert/status_code": AssertionType.STATUS_CODE,
    "assert/exact": AssertionType.EXACT,
    "assert/regex": AssertionType.REGEX,
    "assert/greater_than": AssertionType.GREATER_THAN,
    "assert/less_than": AssertionType.LESS_THAN,
    "assert/greater_or_equal": AssertionType.GREATER_OR_EQUAL,
    "assert/less_or_equal": AssertionType.LESS_OR_EQUAL,
    "assert/between": AssertionType.BETWEEN,
    "assert/assert_field": AssertionType.ASSERT_FIELD,
    "assert/json_path_extract": AssertionType.JSON_PATH_EXTRACT,
    # Legacy flat names for backward compatibility.
    "NOT_NULL": AssertionType.NOT_NULL,
    "NOT_EMPTY": AssertionType.NOT_EMPTY,
    "EQUALS": AssertionType.EQUALS,
    "STATUS_CODE": AssertionType.STATUS_CODE,
    "CONTAINS": AssertionType.CONTAINS,
    "SCHEMA": AssertionType.SCHEMA,
    "SCHEMA_VALIDATION": AssertionType.SCHEMA_VALIDATION,
    "REGEX": AssertionType.REGEX,
    "JSON_PATH_EXTRACT": AssertionType.JSON_PATH_EXTRACT,
}


def _extract_params(assertion: Assertion) -> dict:
    """Extract runtime parameters from an ``Assertion.with_`` dict."""
    return assertion.with_ or {}


def _apply_inline_operator(operator: str, actual: object, expected: object) -> tuple[bool, str]:
    """Apply a named operator for validate/assert inline assertions."""
    if operator == "not_null":
        return actual is not None, "Expected non-null value, got None"
    if operator == "null":
        return actual is None, f"Expected null, got {actual!r}"
    if operator == "not_empty":
        return bool(actual), f"Expected non-empty value, got {actual!r}"
    if operator == "equals":
        passed = actual == expected or str(actual) == str(expected)
        return passed, f"Expected {expected!r}, got {actual!r}"
    if operator == "not_equals":
        passed = actual != expected and str(actual) != str(expected)
        return passed, f"Expected value != {expected!r}, got {actual!r}"
    if operator == "contains":
        passed = str(expected) in str(actual) if actual is not None else False
        return passed, f"Expected {actual!r} to contain {expected!r}"
    if operator == "not_contains":
        passed = str(expected) not in str(actual) if actual is not None else True
        return passed, f"Expected {actual!r} to NOT contain {expected!r}"
    if operator == "matches_regex":
        import re
        passed = isinstance(actual, str) and bool(re.search(str(expected), actual))
        return passed, f"Pattern {expected!r} not matched in {actual!r}"
    return False, f"Unknown operator: {operator!r}"


def _assertion_type(a: Assertion) -> AssertionType:
    """Resolve AssertionType from ``Assertion.uses`` string."""
    resolved = _USES_TO_TYPE.get(a.uses)
    if resolved is None:
        try:
            resolved = AssertionType(a.uses)
        except ValueError:
            resolved = AssertionType.EXACT
    return resolved


class AssertionEngine:
    """Evaluates a list of assertions against a step's output value."""

    @staticmethod
    def evaluate(
        assertions: list[Assertion],
        output: object,
        context_vars: Optional[dict[str, object]] = None,
    ) -> list[AssertionResult]:
        return [
            AssertionEngine._evaluate_one(assertion, output, context_vars or {})
            for assertion in assertions
        ]

    @staticmethod
    def _evaluate_one(
        assertion: Assertion,
        output: object,
        context_vars: dict[str, object],
    ) -> AssertionResult:
        params = _extract_params(assertion)
        a_type = _assertion_type(assertion)

        # Handle validate/assert and validate/field when used inline in
        # a step's validate: block. These use "input" as path and
        # "operator" as the check — not the standard output/path/EXACT flow.
        if assertion.uses in ("validate/assert", "validate/field"):
            return AssertionEngine._evaluate_inline_validate_assert(
                assertion, output, params, context_vars
            )

        if a_type == AssertionType.JSON_PATH_EXTRACT:
            from tractusx_testlab.steps._checks.json_path import (
                evaluate_json_path_extract,
            )
            return evaluate_json_path_extract(
                assertion, output, context_vars,
                extract_actual_fn=AssertionEngine.extract_path,
                evaluate_fn=AssertionEngine.evaluate,
            )

        path = params.get("output") or params.get("path")
        severity = AssertionSeverity(params.get("severity", "HARD"))
        expected = AssertionEngine._resolve_expected(assertion, a_type, params, context_vars)
        actual = AssertionEngine._extract_actual(output, path)

        check = _ASSERTION_CHECKS.get(a_type)
        if check is None:
            passed, message = False, f"Unknown assertion type: {a_type}"
        else:
            passed, message = check(actual, expected, output)

        return AssertionResult(
            assertion=assertion,
            passed=passed,
            expected=expected,
            actual=actual,
            message=message if not passed else "",
            severity=severity,
        )

    @staticmethod
    def _resolve_expected(
        assertion: Assertion,
        a_type: AssertionType,
        params: dict,
        context_vars: dict[str, object],
    ) -> object:
        if a_type == AssertionType.BETWEEN:
            return [params.get("min"), params.get("max")]
        if a_type == AssertionType.SCHEMA_VALIDATION:
            ref = params.get("schema")
            if isinstance(ref, str) and ref.startswith("@"):
                return context_vars.get(ref[1:], ref)
            return ref
        if a_type == AssertionType.ASSERT_FIELD:
            exp_val = params.get("expected")
            if isinstance(exp_val, str) and exp_val.startswith("@"):
                exp_val = context_vars.get(exp_val[1:], exp_val)
            return {"operator": params.get("operator", "equals"), "value": exp_val}
        source = params.get("source", "INLINE")
        val = params.get("value")
        if source == "VARIABLE":
            return context_vars.get(str(val), val)
        if isinstance(val, str) and val.startswith("@"):
            return context_vars.get(val[1:], val)
        return val

    @staticmethod
    def _evaluate_inline_validate_assert(
        assertion: "Assertion",
        output: object,
        params: dict,
        context_vars: dict[str, object],
    ) -> "AssertionResult":
        """Handle validate/assert and validate/field inline in step validate: blocks.

        Uses ``params["input"]`` as the extraction path into the step output,
        and ``params["operator"]`` (default ``not_null``) as the check.
        """
        input_path = params.get("input")
        operator = params.get("operator", "not_null")
        expected = params.get("value")
        severity = AssertionSeverity(params.get("severity", "HARD"))
        actual = AssertionEngine.extract_path(output, input_path)
        passed, message = _apply_inline_operator(operator, actual, expected)
        return AssertionResult(
            assertion=assertion,
            passed=passed,
            expected=expected,
            actual=actual,
            message=message if not passed else "",
            severity=severity,
        )

    @staticmethod
    def extract_path(output: object, path: Optional[str]) -> object:
        """Extract a value from a nested dict/list/object using dot-separated *path*."""
        return extract_path(output, path)

    # Keep old name as internal alias for backward compatibility
    _extract_actual = staticmethod(extract_path)

    @staticmethod
    def has_hard_failure(results: list[AssertionResult]) -> bool:
        return any(
            not result.passed and result.severity == AssertionSeverity.HARD
            for result in results
        )

    @staticmethod
    def build_summary(step_results: list[StepResult]) -> AssertionSummary:
        """Aggregate assertion counts across step results."""
        total = passed = failed_hard = failed_soft = 0
        for step_result in step_results:
            for assertion_result in step_result.assertions:
                total += 1
                if assertion_result.passed:
                    passed += 1
                elif assertion_result.severity.value == "HARD":
                    failed_hard += 1
                else:
                    failed_soft += 1
        return AssertionSummary(
            total=total, passed=passed,
            failed_hard=failed_hard, failed_soft=failed_soft,
        )


# Dispatch table mapping assertion types to their check functions.
_ASSERTION_CHECKS = {
    AssertionType.EXACT: _checks.check_exact,
    AssertionType.STATUS_CODE: _checks.check_status_code,
    AssertionType.CONTAINS: _checks.check_contains,
    AssertionType.REGEX: _checks.check_regex,
    AssertionType.SCHEMA: _checks.check_schema,
    AssertionType.NOT_NULL: _checks.check_not_null,
    AssertionType.NOT_EMPTY: _checks.check_not_empty,
    AssertionType.EQUALS: _checks.check_equals,
    AssertionType.NOT_EQUALS: _checks.check_not_equals,
    AssertionType.NOT_CONTAINS: _checks.check_not_contains,
    AssertionType.SCHEMA_VALIDATION: _checks.check_schema_validation,
    AssertionType.GREATER_THAN: _checks.check_greater_than,
    AssertionType.LESS_THAN: _checks.check_less_than,
    AssertionType.GREATER_OR_EQUAL: _checks.check_greater_or_equal,
    AssertionType.LESS_OR_EQUAL: _checks.check_less_or_equal,
    AssertionType.BETWEEN: _checks.check_between,
    AssertionType.ASSERT_FIELD: _checks.check_assert_field,
}

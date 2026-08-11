#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""json_path_extract validation type — extracts and validates nested values inline."""

from __future__ import annotations

from typing import Any

from tractusx_testlab.models import AssertionSeverity
from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.models.runtime.results import AssertionResult
from tractusx_testlab.steps.utility.json_extract import _extract_by_path


def evaluate_json_path_extract(
    assertion: Assertion,
    output: Any,
    context_vars: dict,
    extract_actual_fn: Any,
    evaluate_fn: Any,
) -> AssertionResult:
    """Handle json_path_extract as a validation type."""
    params = assertion.with_ or {}
    source_name = params.get("output") or params.get("path")
    if source_name and source_name in context_vars:
        data = context_vars[source_name]
    else:
        data = extract_actual_fn(output, source_name)

    json_path = params.get("json_path")
    severity_str = params.get("severity", "HARD")
    severity = AssertionSeverity(severity_str)

    if not json_path:
        return AssertionResult(
            assertion=assertion,
            passed=False,
            expected="json_path field required",
            actual=None,
            message="json_path_extract validation requires 'json_path' field",
            severity=severity,
        )

    try:
        extracted = _extract_by_path(data, json_path)
    except (KeyError, IndexError, TypeError) as exc:
        return AssertionResult(
            assertion=assertion,
            passed=False,
            expected=f"value at path '{json_path}'",
            actual=None,
            message=f"json_path extraction failed: {exc}",
            severity=severity,
        )

    store_in = params.get("store_in_variable")
    if store_in:
        context_vars[store_in] = extracted

    nested = params.get("validate") or params.get("nested_validate") or []
    if nested:
        nested_assertions = [
            Assertion.model_validate(n) if isinstance(n, dict) else n
            for n in nested
        ]
        nested_results = evaluate_fn(nested_assertions, extracted, context_vars)
        all_passed = all(r.passed for r in nested_results)
        return AssertionResult(
            assertion=assertion,
            passed=all_passed,
            expected=None,
            actual=extracted,
            message="" if all_passed else "Nested validation failed",
            severity=severity,
        )

    return AssertionResult(
        assertion=assertion,
        passed=True,
        expected=None,
        actual=extracted,
        message="",
        severity=severity,
    )

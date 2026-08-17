################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""The ``validate/*`` vocabulary — every spelling a TCK may write, and what it does.

These cover the drift that let three IDE-authored assertions compile and then
fail against a healthy SUT: ``between`` had no operator, ``validate/schema`` fell
back to an exact match, and ``validate/field`` ignored its ``path``.
"""

from __future__ import annotations

import pytest

from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.steps.assertions import (
    OPERATORS,
    AssertionEngine,
    AssertionKind,
    apply_operator,
    resolve,
)


def _assert(uses: str, **params: object) -> Assertion:
    return Assertion(uses=uses, **{"with": params})


def _run(step_output: object, uses: str, **params: object):
    return AssertionEngine.evaluate([_assert(uses, **params)], step_output)[0]


class TestOperatorVocabulary:
    """The operator table is the single source of truth for comparisons."""

    def test_the_ratified_operator_set_is_complete(self) -> None:
        assert OPERATORS == {
            "not_null", "is_null", "not_empty",
            "equals", "not_equals", "contains", "not_contains", "matches_regex",
            "one_of", "none_of", "has_key", "not_has_key",
            "gt", "gte", "lt", "lte",
            "length_equals", "length_gt", "length_lt",
            "between",
        }

    @pytest.mark.parametrize("operator", sorted(OPERATORS))
    def test_every_declared_operator_is_actually_dispatched(self, operator: str) -> None:
        _, message = apply_operator(operator, None, None)
        assert "Unknown operator" not in message

    def test_an_unknown_operator_says_so(self) -> None:
        passed, message = apply_operator("approximately", 1, 1)
        assert not passed
        assert "Unknown operator" in message


class TestBetween:
    """``between`` reads min/max — the IDE's assert_between block emits exactly this."""

    def test_a_value_inside_the_range_passes(self) -> None:
        result = _run({"status_code": 204}, "validate/assert",
                      input="status_code", operator="between", min=200, max=299)
        assert result.passed, result.message

    def test_a_value_outside_the_range_fails(self) -> None:
        result = _run({"status_code": 500}, "validate/assert",
                      input="status_code", operator="between", min=200, max=299)
        assert not result.passed
        assert "between" in result.message

    def test_a_missing_bound_is_reported_not_ignored(self) -> None:
        result = _run({"status_code": 204}, "validate/assert",
                      input="status_code", operator="between", min=200)
        assert not result.passed
        assert "min" in result.message and "max" in result.message

    def test_the_suffix_spelling_means_the_same_thing(self) -> None:
        result = _run({"status_code": 204}, "validate/assert/between",
                      input="status_code", min=200, max=299)
        assert result.passed, result.message


class TestSchema:
    """``validate/schema`` validates; it does not compare the payload to nothing."""

    _SCHEMA = {
        "type": "object",
        "required": ["id"],
        "properties": {"id": {"type": "string"}},
    }

    def test_a_conforming_payload_passes(self) -> None:
        result = _run({"response_body": {"id": "abc"}}, "validate/schema",
                      input="response_body", schema=self._SCHEMA)
        assert result.passed, result.message

    def test_a_non_conforming_payload_fails_for_the_right_reason(self) -> None:
        result = _run({"response_body": {"id": 42}}, "validate/schema",
                      input="response_body", schema=self._SCHEMA)
        assert not result.passed
        assert "Schema validation failed" in result.message

    def test_a_missing_schema_names_the_missing_key(self) -> None:
        result = _run({"response_body": {"id": "abc"}}, "validate/schema",
                      input="response_body")
        assert not result.passed
        assert "schema" in result.message


class TestFieldPath:
    """``validate/field`` descends ``path`` inside ``input`` — the block's two fields."""

    _OUTPUT = {"response_body": {"header": {"messageId": "m-1"}, "content": []}}

    def test_the_path_selects_the_nested_field(self) -> None:
        result = _run(self._OUTPUT, "validate/field",
                      input="response_body", path="header.messageId",
                      operator="equals", value="m-1")
        assert result.passed, result.message
        assert result.actual == "m-1"

    def test_a_wrong_expectation_at_the_path_fails(self) -> None:
        result = _run(self._OUTPUT, "validate/field",
                      input="response_body", path="header.messageId",
                      operator="equals", value="m-2")
        assert not result.passed
        assert result.actual == "m-1"

    def test_without_a_path_the_whole_input_is_the_subject(self) -> None:
        result = _run(self._OUTPUT, "validate/field",
                      input="response_body", operator="not_null")
        assert result.passed, result.message
        assert result.actual == self._OUTPUT["response_body"]


class TestUnknownAssertions:
    """An assertion the engine cannot resolve fails loudly, never silently."""

    def test_an_unknown_uses_is_reported(self) -> None:
        result = _run({"a": 1}, "assert/equals", output="a", value=1)
        assert not result.passed
        assert "Unknown assertion" in result.message

    def test_the_deleted_assert_family_no_longer_resolves(self) -> None:
        for uses in ("assert/not_null", "assert/status_code", "assert/schema_validation"):
            assert isinstance(resolve(uses, {}), str), f"{uses} should not resolve"

    def test_an_unknown_operator_is_reported(self) -> None:
        result = _run({"a": 1}, "validate/assert", input="a", operator="approximately")
        assert not result.passed
        assert "Unknown operator" in result.message


class TestResolution:
    """Both spellings of a check resolve to the same thing."""

    def test_the_suffix_and_the_operator_key_agree(self) -> None:
        from_suffix = resolve("validate/assert/equals", {})
        from_key = resolve("validate/assert", {"operator": "equals"})
        assert from_suffix == from_key
        assert from_suffix.kind is AssertionKind.ASSERT

    def test_an_assert_without_an_operator_checks_for_a_value(self) -> None:
        assert resolve("validate/assert", {}).operator == "not_null"

    def test_schema_takes_no_operator(self) -> None:
        assert resolve("validate/schema", {}).operator is None

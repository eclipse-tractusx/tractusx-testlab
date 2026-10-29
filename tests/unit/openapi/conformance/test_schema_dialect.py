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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""OpenAPI 3.0 schemas read with their 3.0 meaning; 3.1 schemas as written."""

from __future__ import annotations

import pytest

from tests.unit.openapi.documents import bound, shop, shop_raw
from tractusx_testlab.openapi.conformance import schema_problems
from tractusx_testlab.openapi.conformance.schema_dialect import to_2020_12

_MATERIAL = "#/components/schemas/Material"


def _errors(value: object, document=None) -> list[str]:
    return [p.keyword for p in schema_problems(document or shop(), _MATERIAL, value)]


class TestNullable:
    def test_null_is_allowed_where_nullable_is_true(self) -> None:
        assert _errors({"id": "m", "share": None}) == []

    def test_null_is_refused_where_it_is_not(self) -> None:
        assert _errors({"id": None, "share": 1}) == ["type"]

    def test_a_nullable_ref_wrapped_in_all_of_allows_null(self) -> None:
        assert _errors({"id": "m", "share": 1, "grade": None}) == []
        assert _errors({"id": "m", "share": 1, "grade": "Z"}) == ["anyOf"]

    def test_a_nullable_enum_gains_null(self) -> None:
        assert to_2020_12({"enum": ["a"], "type": "string", "nullable": True}) == {
            "enum": ["a", None],
            "type": ["string", "null"],
        }


class TestExclusiveBounds:
    def test_a_boolean_exclusive_minimum_excludes_the_minimum(self) -> None:
        assert _errors({"id": "m", "share": 0}) == ["exclusiveMinimum"]
        assert _errors({"id": "m", "share": 0.1}) == []

    def test_a_false_flag_keeps_the_inclusive_bound(self) -> None:
        assert to_2020_12({"minimum": 1, "exclusiveMinimum": False}) == {"minimum": 1}

    def test_the_maximum_is_translated_too(self) -> None:
        assert to_2020_12({"maximum": 5, "exclusiveMaximum": True}) == {"exclusiveMaximum": 5}


def test_keywords_beside_a_ref_are_ignored_in_3_0() -> None:
    assert to_2020_12({"$ref": "#/x", "description": "d", "type": "integer"}) == {"$ref": "#/x"}


def test_a_3_1_document_is_validated_as_written() -> None:
    raw = shop_raw()
    raw["openapi"] = "3.1.0"
    raw["components"]["schemas"]["Material"]["properties"]["share"] = {
        "type": ["number", "null"],
        "exclusiveMinimum": 0,
    }
    document = bound(raw, "shop31")
    assert _errors({"id": "m", "share": None}, document) == []
    assert _errors({"id": "m", "share": 0}, document) == ["exclusiveMinimum"]


@pytest.mark.parametrize("value", [{"id": "m", "share": 1, "supplier": {}}])
def test_a_problem_names_where_the_keyword_is_in_the_document(value: object) -> None:
    (problem,) = schema_problems(shop(), _MATERIAL, value)
    assert problem.pointer == "/supplier"
    assert problem.keyword == "required"
    assert problem.schema_location == "#/components/schemas/Supplier/required"

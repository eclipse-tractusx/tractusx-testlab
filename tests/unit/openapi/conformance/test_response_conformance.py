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

"""Checking an answer against its operation: status, expect, type, body, headers."""

from __future__ import annotations

import json

import pytest

from tests.unit.openapi.documents import bound, ich, shop, shop_raw
from tractusx_testlab.logging.masking import forget_secrets, register_secret
from tractusx_testlab.openapi.conformance import check_response, expect_matches
from tractusx_testlab.openapi.operations import operation_index

_JSON = {"Content-Type": "application/json", "X-Rate-Limit": "10"}


def _check(name: str, status: int, body: object = None, headers=None, **kwargs: object):
    document = shop()
    return check_response(
        document,
        operation_index(document).find(name),
        status=status,
        headers=_JSON if headers is None else headers,
        body=body,
        **kwargs,  # type: ignore[arg-type]
    )


def _checks(verdict) -> list[str]:
    return [p.check for p in verdict.problems]


class TestStatus:
    def test_a_documented_status_with_a_valid_body_passes(self) -> None:
        verdict = _check("getMaterial", 200, {"id": "m", "share": 1})
        assert verdict.passed, verdict.problems

    def test_a_status_class_documents_its_statuses(self) -> None:
        problem = {"title": "x", "status": 404}
        assert _check(
            "getMaterial", 404, problem, {"Content-Type": "application/problem+json"}
        ).passed

    def test_default_documents_any_other_status(self) -> None:
        assert _check("getMaterial", 503, None, {}).passed

    def test_an_undocumented_status_fails(self) -> None:
        verdict = _check("listMaterials", 500, None, {})
        assert _checks(verdict) == ["status"]
        assert "documented: 200" in verdict.problems[0].message

    def test_an_exact_status_wins_over_its_class(self) -> None:
        verdict = _check(
            "deleteMaterial",
            404,
            {"title": "t", "status": 404},
            {"Content-Type": "application/json"},
        )
        assert verdict.passed


class TestExpect:
    @pytest.mark.parametrize(
        ("status", "expect", "matches"),
        [
            (200, 200, True),
            (201, "2XX", True),
            (404, "4XX", True),
            (500, "4XX", False),
            (204, "success", True),
            (302, "success", False),
            (400, "error", True),
            (503, "error", True),
            (200, None, True),
            (200, "200", True),
        ],
    )
    def test_expect_forms(self, status: int, expect: object, matches: bool) -> None:
        assert expect_matches(status, expect) is matches

    def test_another_status_than_expected_fails_the_check(self) -> None:
        verdict = _check("getMaterial", 200, {"id": "m", "share": 1}, expect=404)
        assert _checks(verdict) == ["expect"]


class TestContentType:
    def test_an_undocumented_media_type_fails(self) -> None:
        verdict = _check(
            "getMaterial", 200, "<x/>", {"Content-Type": "text/xml", "X-Rate-Limit": "1"}
        )
        assert _checks(verdict) == ["content_type"]

    def test_either_of_two_documented_media_types_passes(self) -> None:
        body = {"title": "t", "status": 400}
        for media in ("application/json", "application/problem+json; charset=utf-8"):
            assert _check("createMaterial", 400, body, {"Content-Type": media}).passed

    def test_a_documented_body_that_did_not_arrive_fails(self) -> None:
        assert _checks(_check("getMaterial", 200, None)) == ["content_type"]

    def test_a_body_where_none_is_documented_fails(self) -> None:
        assert _checks(_check("createMaterial", 201, {"x": 1})) == ["content_type"]

    def test_a_204_without_a_body_passes(self) -> None:
        assert _check("deleteMaterial", 204, None, {}).passed

    def test_a_non_json_media_type_is_not_parsed(self) -> None:
        assert _check("health", 200, "up", {"Content-Type": "text/plain"}).passed


class TestBody:
    def test_every_body_problem_is_reported_with_its_location(self) -> None:
        verdict = _check("getMaterial", 200, {"share": "x", "supplier": {}})
        located = {(p.pointer, p.keyword, p.schema_location) for p in verdict.problems}
        assert located == {
            ("", "required", "#/components/schemas/Material/required"),
            ("/share", "type", "#/components/schemas/Material/properties/share/type"),
            ("/supplier", "required", "#/components/schemas/Supplier/required"),
        }

    def test_text_that_is_not_json_fails(self) -> None:
        verdict = _check("getMaterial", 200, "{not json")
        assert _checks(verdict) == ["body"]
        assert "not valid JSON" in verdict.problems[0].message

    def test_a_json_text_body_is_parsed(self) -> None:
        assert _check("getMaterial", 200, json.dumps({"id": "m", "share": 2})).passed

    def test_a_received_value_is_clipped_and_masked(self) -> None:
        forget_secrets()
        register_secret("s3cr3t-value-0123456789", explicit=True)
        try:
            verdict = _check("getMaterial", 200, {"id": 1, "share": 1, "note": "x" * 500})
            verdict2 = _check(
                "getMaterial", 200, {"id": "s3cr3t-value-0123456789x" * 1, "share": "a"}
            )
        finally:
            forget_secrets()
        assert all(len(p.received or "") <= 80 for p in verdict.problems)
        assert "s3cr3t-value-0123456789" not in json.dumps([p.as_dict() for p in verdict2.problems])

    def test_a_value_under_a_credential_name_is_never_quoted(self) -> None:
        raw = shop_raw()
        raw["components"]["schemas"]["Material"]["properties"]["password"] = {"type": "integer"}
        document = bound(raw, "secretive")
        verdict = check_response(
            document,
            operation_index(document).find("getMaterial"),
            status=200,
            headers=_JSON,
            body={"id": "m", "share": 1, "password": "hunter2-hunter2"},
        )
        (problem,) = verdict.problems
        assert problem.received == "***"
        assert "hunter2" not in json.dumps(problem.as_dict())


class TestHeaders:
    def test_a_required_response_header_must_be_there(self) -> None:
        verdict = _check(
            "getMaterial", 200, {"id": "m", "share": 1}, {"Content-Type": "application/json"}
        )
        assert _checks(verdict) == ["headers"]

    def test_header_names_are_matched_in_any_case(self) -> None:
        headers = {"content-type": "application/json", "x-rate-limit": "1"}
        assert _check("getMaterial", 200, {"id": "m", "share": 1}, headers).passed


class TestDataPlane:
    @pytest.mark.parametrize("status", [401, 403, 502, 504])
    def test_a_data_plane_status_is_reported_as_the_data_planes(self, status: int) -> None:
        verdict = _check("listMaterials", status, None, {}, data_plane=True)
        assert _checks(verdict) == ["data_plane"]
        assert "never asked" in verdict.problems[0].message

    def test_an_expected_data_plane_refusal_passes(self) -> None:
        assert _check("listMaterials", 403, None, {}, data_plane=True, expect=403).passed

    def test_without_data_plane_the_status_is_checked_against_the_document(self) -> None:
        assert _checks(_check("listMaterials", 403, None, {})) == ["status"]


def test_the_ich_document_checks_a_real_answer() -> None:
    document = ich()
    operation = operation_index(document).find(
        "GET /v1/partner-management/business-partner/{business_partner_number}"
    )
    good = check_response(
        document,
        operation,
        status=200,
        headers={"content-type": "application/json"},
        body={"name": "ACME", "bpnl": "BPNL000000000001"},
    )
    bad = check_response(
        document,
        operation,
        status=200,
        headers={"content-type": "application/json"},
        body={"name": 5},
    )
    assert good.passed
    assert (
        "#/components/schemas/BusinessPartnerRead/properties/name/type" in bad.problems[0].message
    )

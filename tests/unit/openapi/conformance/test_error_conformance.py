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

"""Error answers judged together: one format, no leaks, no 5xx for a client error."""

from __future__ import annotations

from tests.unit.openapi.documents import shop
from tractusx_testlab.openapi.conformance import ErrorAnswer, error_problems
from tractusx_testlab.openapi.operations import operation_index

_PROBLEM = {"Content-Type": "application/problem+json"}


def _answer(
    status: int, body: object, headers=None, expect=None, name: str = "getMaterial"
) -> ErrorAnswer:
    document = shop()
    return ErrorAnswer(
        label=name,
        status=status,
        headers=_PROBLEM if headers is None else headers,
        body=body,
        expect=expect,
        document=document,
        operation=operation_index(document).find(name),
    )


def _checks(found) -> list[str]:
    return [problem.check for _, problem in found]


class TestFormat:
    def test_bodies_matching_their_declared_schema_pass(self) -> None:
        assert error_problems([_answer(404, {"title": "t", "status": 404})]) == []

    def test_a_body_off_its_declared_schema_fails(self) -> None:
        assert _checks(error_problems([_answer(404, {"message": "nope"})])) == ["format", "format"]

    def test_a_success_answer_is_not_judged(self) -> None:
        assert (
            error_problems([_answer(200, {"anything": 1}, {"Content-Type": "application/json"})])
            == []
        )

    def test_problem_json_requires_the_media_type_and_the_matching_status(self) -> None:
        found = error_problems(
            [_answer(404, {"title": "t", "status": 400}, {"Content-Type": "application/json"})],
            error_format="problem+json",
        )
        messages = [problem.message for _, problem in found]
        assert any("not application/problem+json" in m for m in messages)
        assert any("member 'status' is 400" in m for m in messages)

    def test_problem_json_types_its_members(self) -> None:
        found = error_problems([_answer(404, {"title": 5})], error_format="problem+json")
        assert [(p.pointer, p.keyword) for _, p in found] == [("/title", "type")]

    def test_one_given_schema_holds_every_error(self) -> None:
        schema = {"type": "object", "required": ["code"]}
        found = error_problems(
            [_answer(404, {"code": "X"}), _answer(400, {"title": "t", "status": 400})],
            schema=schema,
        )
        assert [(a.status, p.keyword) for a, p in found] == [(400, "required")]

    def test_a_body_that_is_not_json_fails_a_given_schema(self) -> None:
        found = error_problems([_answer(500, "oops", {})], schema={"type": "object"})
        assert [p.message for _, p in found] == ["the body is not JSON"]


class TestLeaksAndClientErrors:
    def test_a_leaking_error_body_is_reported(self) -> None:
        body = {"title": "t", "status": 500, "detail": "java.lang.NullPointerException at x"}
        found = error_problems([_answer(500, body, expect=None)], schema={"type": "object"})
        assert _checks(found) == ["leaks"]

    def test_leaks_can_be_left_unchecked(self) -> None:
        body = {"detail": "java.lang.NullPointerException"}
        assert error_problems([_answer(500, body)], schema={}, check_leaks=False) == []

    def test_a_5xx_for_a_request_sent_wrong_on_purpose_fails(self) -> None:
        for expect in (400, "4XX", "error"):
            found = error_problems([_answer(500, {}, expect=expect)], schema={})
            assert _checks(found) == ["client_errors"], expect

    def test_a_5xx_nobody_provoked_is_not_a_client_error(self) -> None:
        assert error_problems([_answer(503, {}, expect=None)], schema={}) == []

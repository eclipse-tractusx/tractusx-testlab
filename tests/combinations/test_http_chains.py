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

"""Chains that make a real HTTP call and then work on what came back.

Every request here reaches a socket. A step that builds a URL out of a
reference which never resolved sends that literal text to the server, and the
server says so — which is the whole reason these are not run against a mock.
"""

from __future__ import annotations

import pytest

from combinations.harness import Harness
from combinations.http_double import HttpDouble, Response

pytestmark = pytest.mark.asyncio


class TestRequestThenExtract:
    """Call an endpoint, pull one field out of the answer, use it."""

    async def test_a_field_of_the_response_becomes_the_next_steps_input(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route(
            "GET", "/twins", {"result": [{"id": "urn:uuid:1", "idShort": "gearbox"}]}
        )
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/twins"},
                "returns": {"response_body": {"type": "object"}},
            },
            {
                "id": "pick",
                "uses": "util/json_path_extract",
                "with": {
                    "input": "${{ execution.fetch.response_body }}",
                    "path": "result.0.id",
                },
                "returns": {"value": {"type": "string"}},
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.pick.value }}"},
            },
        )

        assert outcome.passed, outcome.failures
        assert outcome.output("echo") == "urn:uuid:1"

    async def test_a_resolved_reference_reaches_the_server_as_a_real_url(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """The request the step built is the request the socket received."""
        http.json_route("GET", "/twins/urn:uuid:7", {"idShort": "axle"})
        base = http.start()
        harness.seed(twin_id="urn:uuid:7")

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/twins/${{{{ env.twin_id }}}}"},
                "returns": {"status_code": {"type": "integer"}},
            },
        )

        assert outcome.variables["status_code"] == 200
        assert [r.path for r in http.received] == ["/twins/urn:uuid:7"]

    async def test_a_generated_id_travels_into_the_request_body(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """A reference embedded in a longer string is interpolated, not replaced.

        The whole-string form returns the raw value with its type intact; a
        reference spliced into surrounding text is a different code path, and
        the one a URN prefix goes through.
        """
        http.json_route("POST", "/twins", {"created": True}, status=201)
        base = http.start()

        outcome = await harness.run(
            {
                "id": "mint",
                "uses": "util/generate_bpn",
                "returns": {"bpn": {"type": "string"}},
            },
            {
                "id": "create",
                "uses": "http/http_request",
                "with": {
                    "method": "POST",
                    "url": f"{base}/twins",
                    "body": {"id": "urn:bpn:${{ execution.mint.bpn }}", "idShort": "axle"},
                },
                "returns": {"status_code": {"type": "integer"}},
            },
        )

        minted = outcome.output("mint")["bpn"]
        assert outcome.variables["status_code"] == 201
        assert http.calls_to("POST", "/twins")[0].body == {
            "id": f"urn:bpn:{minted}",
            "idShort": "axle",
        }


class TestRequestThenAssert:
    """The ``validate:`` block reads the same output the next step would."""

    async def test_assertions_run_against_the_declared_returns(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/state", {"state": "FINALIZED", "attempts": 3})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/state"},
                "returns": {
                    "status_code": {"type": "integer"},
                    "response_body": {"type": "object"},
                },
                "validate": [
                    {
                        "uses": "validate/assert",
                        "with": {
                            "input": "status_code",
                            "operator": "equals",
                            "value": 200,
                        },
                    },
                    {
                        "uses": "validate/field",
                        "with": {
                            "input": "response_body",
                            "path": "state",
                            "operator": "one_of",
                            "value": ["FINALIZED", "COMPLETED"],
                        },
                    },
                    {
                        "uses": "validate/field/between",
                        "with": {
                            "input": "response_body",
                            "path": "attempts",
                            "min": 1,
                            "max": 5,
                        },
                    },
                ],
            },
        )

        assert outcome.passed, outcome.assertion_messages("fetch")

    async def test_a_failing_assertion_fails_the_step(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/state", {"state": "TERMINATED"})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/state"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/field",
                        "with": {
                            "input": "response_body",
                            "path": "state",
                            "operator": "equals",
                            "value": "FINALIZED",
                        },
                    },
                ],
            },
        )

        assert not outcome.passed
        assert "TERMINATED" in " ".join(outcome.assertion_messages("fetch"))

    async def test_a_failed_step_still_publishes_what_it_produced(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """An assertion failing does not erase the response it failed on.

        A teardown step reading the id of the thing that was created still
        needs it when the check on it failed.
        """
        http.json_route("POST", "/assets", {"@id": "asset-9"}, status=200)
        base = http.start()

        outcome = await harness.run(
            {
                "id": "create",
                "uses": "http/http_request",
                "with": {"method": "POST", "url": f"{base}/assets", "body": {}},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/assert",
                        "with": {
                            "input": "status_code",
                            "operator": "equals",
                            "value": 201,
                        },
                    },
                ],
            },
            {
                "id": "read_back",
                "uses": "util/json_path_extract",
                "with": {
                    "input": "${{ execution.create.response_body }}",
                    "path": "@id",
                },
            },
        )

        assert not outcome.result("create").status.value == "passed"
        assert outcome.output("read_back") == "asset-9"


class TestStatusCodesThatAreNotErrors:
    """A 4xx is an answer, not a crash — the script decides what it means."""

    async def test_a_404_is_reported_and_assertable(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route("GET", "/gone", Response(status=404, body={"error": "not found"}))
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/gone"},
                "returns": {"status_code": {"type": "integer"}},
                "validate": [
                    {
                        "uses": "validate/assert",
                        "with": {
                            "input": "status_code",
                            "operator": "equals",
                            "value": 404,
                        },
                    },
                ],
            },
        )

        assert outcome.passed, outcome.assertion_messages("fetch")
        assert outcome.variables["status_code"] == 404

    async def test_a_response_header_is_readable_downstream(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.route(
            "GET",
            "/paged",
            Response(status=200, body={"items": []}, headers={"X-Next-Cursor": "c2"}),
        )
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/paged"},
                "returns": {"response_headers": {"type": "object"}},
            },
            {
                "id": "cursor",
                "uses": "util/json_path_extract",
                "with": {
                    "input": "${{ execution.fetch.response_headers }}",
                    "path": "X-Next-Cursor",
                },
            },
        )

        assert outcome.output("cursor") == "c2"

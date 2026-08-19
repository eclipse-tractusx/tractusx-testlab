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

"""A mock handler sees the query it was sent, repeats included."""

from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from tractusx_testlab.server.mock_registry import MockRequest, query_of


class TestQueryOf:
    def test_a_repeated_name_keeps_every_value_in_order(self) -> None:
        """``?assetIds=a&assetIds=b`` is one request with two criteria."""
        assert query_of([("assetIds", "a"), ("assetIds", "b")]) == {"assetIds": ["a", "b"]}

    def test_a_name_given_once_is_a_list_of_one(self) -> None:
        assert query_of([("state", "FINALIZED")]) == {"state": ["FINALIZED"]}

    def test_no_query_is_no_names(self) -> None:
        assert query_of([]) == {}


class TestMockRequestReading:
    def _request(self, query: dict[str, list[str]]) -> MockRequest:
        return MockRequest(
            method="GET", path="/lookup/shells", headers={}, query_params=query, body=None
        )

    def test_query_reads_the_single_value_a_handler_asked_for(self) -> None:
        assert self._request({"cursor": ["abc"]}).query("cursor") == "abc"

    def test_query_of_a_name_that_was_not_sent_is_none(self) -> None:
        assert self._request({}).query("cursor") is None

    def test_query_all_reads_every_value(self) -> None:
        assert self._request({"assetIds": ["a", "b"]}).query_all("assetIds") == ["a", "b"]

    def test_query_all_of_a_name_that_was_not_sent_is_empty(self) -> None:
        assert self._request({}).query_all("assetIds") == []


class TestWhatTheServerHandsOver:
    """The assumption the routes rest on: the framework keeps repeated values.

    ``dict(request.query_params)`` keeps only the last, which is how a lookup
    with two criteria became a lookup with one. This pins the call that does not.
    """

    def test_the_route_sees_every_value_of_a_repeated_parameter(self) -> None:
        app = FastAPI()

        @app.get("/echo")
        async def echo(request: Request) -> dict:
            return query_of(request.query_params.multi_items())

        with TestClient(app) as client:
            answer = client.get("/echo?assetIds=a&assetIds=b&cursor=1").json()

        assert answer == {"assetIds": ["a", "b"], "cursor": ["1"]}

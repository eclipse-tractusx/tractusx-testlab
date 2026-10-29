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

"""Building a request from an operation: encoded, complete, and nowhere but base_url."""

from __future__ import annotations

import pytest

from tests.unit.openapi.documents import bound, shop, shop_raw
from tractusx_testlab.openapi.operations import (
    ApiRequestError,
    default_server_url,
    operation_index,
    prepare,
    server_base_path,
)

_BASE = "https://shop.example/api/v1"


def _prepare(name: str, **kwargs: object):
    operation = operation_index(shop()).find(name)
    values = {"base_url": _BASE, "path_params": {}, "query": {}, "headers": {}, **kwargs}
    return prepare(operation, **values)  # type: ignore[arg-type]


def _problems(name: str, **kwargs: object) -> list[str]:
    with pytest.raises(ApiRequestError) as caught:
        _prepare(name, **kwargs)
    return list(caught.value.problems)


class TestPath:
    def test_a_placeholder_is_encoded_as_one_segment(self) -> None:
        request = _prepare("getMaterial", path_params={"id": "a/b c?d#e"})
        assert request.url == f"{_BASE}/materials/a%2Fb%20c%3Fd%23e"

    @pytest.mark.parametrize("value", [".", "..", ""])
    def test_a_value_that_would_leave_its_segment_is_refused(self, value: str) -> None:
        assert any("may not be" in p for p in _problems("getMaterial", path_params={"id": value}))

    def test_a_missing_placeholder_is_refused_before_sending(self) -> None:
        assert _problems("getMaterial") == ["path parameter 'id' is required and was not given"]

    def test_an_unknown_placeholder_is_refused(self) -> None:
        problems = _problems("getMaterial", path_params={"id": "1", "idd": "2"})
        assert problems == ["path parameter 'idd' is not in '/materials/{id}'"]

    def test_numbers_and_booleans_are_written_as_text(self) -> None:
        assert _prepare("getMaterial", path_params={"id": True}).path == "/materials/true"
        assert _prepare("getMaterial", path_params={"id": 7}).path == "/materials/7"


class TestQueryAndHeaders:
    def test_a_required_query_parameter_is_refused_when_missing(self) -> None:
        assert _problems("listMaterials") == [
            "query parameter 'limit' is required and was not given"
        ]

    def test_a_list_repeats_the_parameter(self) -> None:
        request = _prepare("listMaterials", query={"limit": 2, "tag": ["a", "b"]})
        assert request.query == [("limit", "2"), ("tag", "a"), ("tag", "b")]

    def test_an_object_is_not_a_query_value(self) -> None:
        problems = _problems("listMaterials", query={"limit": {"a": 1}})
        assert "must be a string" in problems[0]

    @pytest.mark.parametrize("value", ["a\r\nX-Injected: 1", "a\nb", "a\x00"])
    def test_a_header_value_that_would_split_the_request_is_refused(self, value: str) -> None:
        problems = _problems("getMaterial", path_params={"id": "1"}, headers={"X-Tenant": value})
        assert problems == ["header 'X-Tenant' has a value with CR, LF or NUL, or is not text"]
        assert value not in " ".join(problems)

    def test_a_header_name_must_be_a_token(self) -> None:
        problems = _problems("getMaterial", path_params={"id": "1"}, headers={"Bad Name": "x"})
        assert "not a valid HTTP header name" in problems[0]

    @pytest.mark.parametrize("value", ["a\r\nb", "a\x00"])
    def test_a_query_or_path_value_with_cr_lf_is_refused(self, value: str) -> None:
        assert _problems("getMaterial", path_params={"id": value})
        assert _problems("listMaterials", query={"limit": value})

    def test_accept_defaults_to_the_documented_success_media_types(self) -> None:
        assert (
            _prepare("getMaterial", path_params={"id": "1"}).headers["Accept"] == "application/json"
        )

    def test_a_given_accept_wins(self) -> None:
        request = _prepare("getMaterial", path_params={"id": "1"}, accept="text/csv")
        assert request.headers["Accept"] == "text/csv"

    def test_every_problem_is_reported_at_once(self) -> None:
        problems = _problems("createMaterial", base_url="ftp://x", headers={"A": "b\n"})
        assert len(problems) == 3


class TestBody:
    def test_a_required_body_is_refused_when_missing(self) -> None:
        assert _problems("createMaterial") == [
            "the operation requires a request body and none was given"
        ]

    def test_an_object_is_sent_as_json_with_the_documented_type(self) -> None:
        request = _prepare("createMaterial", body={"id": "m", "share": 1})
        assert request.headers["Content-Type"] == "application/json"
        assert request.payload == {"content": b'{"id":"m","share":1}'}

    def test_text_is_sent_as_it_is(self) -> None:
        assert _prepare("createMaterial", body="raw").payload == {"content": b"raw"}

    def test_a_form_body_is_sent_as_form_data(self) -> None:
        request = _prepare(
            "createMaterial", body={"a": 1}, content_type="application/x-www-form-urlencoded"
        )
        assert request.payload == {"data": {"a": "1"}}


class TestBaseUrl:
    @pytest.mark.parametrize(
        "base",
        ["shop.example", "ftp://shop.example", "https://x/a?q=1", "https://x/#f", "https://x /a"],
    )
    def test_only_an_absolute_http_url_is_a_base(self, base: str) -> None:
        assert _problems("health", base_url=base)

    def test_the_first_server_is_the_default(self) -> None:
        assert default_server_url(shop()) == _BASE
        assert server_base_path(shop()) == "/api/v1"

    def test_a_templated_server_is_no_target_but_names_the_base_path(self) -> None:
        raw = shop_raw()
        raw["servers"] = [
            {
                "url": "https://{region}.shop.example/api/v{v}",
                "variables": {"region": {"default": "eu"}, "v": {"default": "2"}},
            }
        ]
        assert default_server_url(bound(raw)) is None
        assert server_base_path(bound(raw)) == "/api/v2"

    @pytest.mark.parametrize("url", ["/api", "{scheme}://x", "file:///etc"])
    def test_a_relative_or_unresolved_server_is_no_default(self, url: str) -> None:
        raw = shop_raw()
        raw["servers"] = [{"url": url}]
        assert default_server_url(bound(raw)) is None

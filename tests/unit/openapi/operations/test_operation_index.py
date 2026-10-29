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

"""The operation index: found by operationId or METHOD /path, built once per document."""

from __future__ import annotations

from tests.unit.openapi.documents import bound, ich, shop, shop_raw
from tractusx_testlab.openapi.operations import operation_index
from tractusx_testlab.openapi.operations.operation_index import split_template


class TestFind:
    def test_an_operation_is_found_by_its_operation_id(self) -> None:
        found = operation_index(shop()).find("getMaterial")
        assert found is not None and found.key == "GET /materials/{id}"

    def test_an_operation_is_found_by_method_and_path_in_any_case_of_method(self) -> None:
        assert operation_index(shop()).find("get /materials/{id}").operation_id == "getMaterial"

    def test_an_unknown_name_finds_nothing_and_suggests_the_closest(self) -> None:
        index = operation_index(shop())
        assert index.find("getMaterials") is None
        assert "getMaterial" in index.suggestions("getMaterials")

    def test_every_ich_operation_is_indexed(self) -> None:
        index = operation_index(ich())
        assert len(index.operations) == 54
        assert len(index.by_id) == 54


class TestParameters:
    def test_path_item_parameters_are_merged_into_each_operation(self) -> None:
        names = {p.name for p in operation_index(shop()).find("getMaterial").parameters}
        assert names == {"id", "X-Tenant", "lang"}

    def test_a_path_parameter_is_always_required(self) -> None:
        raw = shop_raw()
        raw["paths"]["/materials/{id}"]["parameters"][0]["required"] = False
        found = operation_index(bound(raw)).find("getMaterial")
        assert next(p for p in found.parameters if p.name == "id").required

    def test_an_operation_parameter_overrides_the_path_items(self) -> None:
        raw = shop_raw()
        raw["paths"]["/materials/{id}"]["get"]["parameters"].append(
            {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
        )
        found = operation_index(bound(raw)).find("getMaterial")
        ids = [p for p in found.parameters if p.name == "id"]
        assert len(ids) == 1 and ids[0].schema == {"type": "integer"}

    def test_a_referenced_parameter_is_followed(self) -> None:
        raw = shop_raw()
        raw["components"]["parameters"] = {
            "Limit": {"name": "limit", "in": "query", "required": True}
        }
        raw["paths"]["/materials"]["get"]["parameters"] = [
            {"$ref": "#/components/parameters/Limit"}
        ]
        found = operation_index(bound(raw)).find("listMaterials")
        assert [(p.name, p.required) for p in found.parameters] == [("limit", True)]


class TestCache:
    def test_a_document_is_indexed_once(self) -> None:
        document = shop()
        assert operation_index(document) is operation_index(document)

    def test_two_bindings_of_one_file_share_the_index(self) -> None:
        assert operation_index(shop()) is operation_index(shop())


def test_a_template_is_split_into_literals_and_placeholders() -> None:
    assert split_template("/a/{x}/b/{y}") == (("/a/", "x"), ("/b/", "y"))
    assert split_template("/a/{x}.json") == (("/a/", "x"), (".json", None))
    assert split_template("/plain") == (("/plain", None),)

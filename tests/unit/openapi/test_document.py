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

"""Loading an API file: OpenAPI 3.0/3.1 only, self-contained, bounded, cached, read-only."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.paths import FIXTURES_DIR
from tractusx_testlab.openapi import (
    MAX_API_FILE_BYTES,
    ApiDocumentError,
    forget_api_documents,
    load_api_document,
    ref_walk,
)
from tractusx_testlab.openapi import document as loader

_YAML = "application/vnd.oai.openapi"
_JSON = "application/vnd.oai.openapi+json"
ICH = FIXTURES_DIR / "openapi" / "industry-core-hub.yaml"


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    forget_api_documents()
    yield
    forget_api_documents()


def _spec(version: str = "3.0.3", **extra: Any) -> dict[str, Any]:
    return {"openapi": version, "info": {"title": "T", "version": "1"}, "paths": {}, **extra}


def _write(tmp_path: Path, document: Any, name: str = "api.json") -> Path:
    path = tmp_path / name
    text = json.dumps(document) if name.endswith(".json") else yaml.safe_dump(document)
    path.write_text(text, encoding="utf-8")
    return path


def _problems(path: Path, media_type: str = _JSON) -> tuple[str, ...]:
    with pytest.raises(ApiDocumentError) as caught:
        load_api_document(path, media_type)
    return caught.value.problems


class TestVersions:
    def test_the_industry_core_hub_document_loads(self) -> None:
        document = load_api_document(ICH, _YAML)

        assert document.openapi == "3.1.0"
        operations = [
            operation
            for item in document.content["paths"].values()
            for method, operation in item.items()
            if method in {"get", "put", "post", "delete", "patch", "head", "options"}
        ]
        assert len(operations) == 54
        assert len(document.sha256) == 64

    @pytest.mark.parametrize("version", ["3.0.0", "3.0.3", "3.1.0", "3.1.1", "3.1.0-rc1"])
    def test_openapi_3_0_and_3_1_load(self, tmp_path: Path, version: str) -> None:
        assert load_api_document(_write(tmp_path, _spec(version)), _JSON).openapi == version

    def test_a_yaml_file_loads_as_yaml(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _spec(), "api.yaml")
        assert load_api_document(path, "application/yaml").content["info"]["title"] == "T"

    def test_swagger_2_is_refused_with_what_to_do(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"swagger": "2.0", "info": {}, "paths": {}})
        assert _problems(path) == (
            "is Swagger 2.0, which is not supported; convert it to OpenAPI 3.0 or 3.1 first "
            "(e.g. with swagger2openapi)",
        )

    @pytest.mark.parametrize("version", ["2.0", "3.2.0", "4.0.0", "3.1"])
    def test_another_version_is_refused(self, tmp_path: Path, version: str) -> None:
        path = _write(tmp_path, _spec(version))
        assert _problems(path) == (f"is OpenAPI {version}; only 3.0.x and 3.1.x are supported",)

    def test_an_unquoted_version_is_named_as_such(self, tmp_path: Path) -> None:
        path = tmp_path / "api.yaml"
        path.write_text("openapi: 3.0\ninfo: {title: T, version: '1'}\npaths: {}\n")
        assert "quote it" in _problems(path, _YAML)[0]

    def test_a_document_without_a_version_is_not_openapi(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"info": {"title": "T", "version": "1"}})
        assert _problems(path) == ("is not an OpenAPI document: it has no 'openapi' version",)

    def test_a_top_level_list_is_not_openapi(self, tmp_path: Path) -> None:
        assert "top level is not a mapping" in _problems(_write(tmp_path, []))[0]

    def test_every_structural_problem_is_reported_at_once(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"openapi": "3.0.3", "info": {"title": 1}})
        assert _problems(path) == (
            "has no 'info.title' text",
            "has no 'info.version' text",
            "has no 'paths'",
        )

    def test_3_1_needs_paths_webhooks_or_components(self, tmp_path: Path) -> None:
        components_only = {"openapi": "3.1.0", "info": {"title": "T", "version": "1"}}
        assert _problems(_write(tmp_path, components_only)) == (
            "has no 'paths' or 'webhooks' or 'components'",
        )
        path = _write(tmp_path, {**components_only, "components": {}}, "b.json")
        assert load_api_document(path, _JSON).openapi == "3.1.0"


class TestReferences:
    def test_an_internal_reference_resolves(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            _spec(
                paths={
                    "/a/{id}": {
                        "get": {"responses": {"200": {"$ref": "#/components/responses/Ok"}}}
                    }
                },
                components={"responses": {"Ok": {"description": "ok"}}},
            ),
        )
        load_api_document(path, _JSON)

    @pytest.mark.parametrize(
        "ref", ["common.yaml#/components/schemas/A", "https://example.org/a.yaml", "./a.json"]
    )
    def test_an_external_reference_is_refused(self, tmp_path: Path, ref: str) -> None:
        path = _write(tmp_path, _spec(components={"schemas": {"A": {"$ref": ref}}}))
        assert _problems(path) == (
            f"has $ref '{ref}' at /components/schemas/A that points outside the file; an API "
            "file must be self-contained — bundle it into one file first",
        )

    def test_a_reference_to_nothing_names_where_it_sits(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            _spec(paths={"/a/b": {"get": {"responses": {"200": {"$ref": "#/components/x"}}}}}),
        )
        assert _problems(path) == (
            "has $ref '#/components/x' at /paths/~1a~1b/get/responses/200 that names nothing "
            "in the file",
        )

    def test_an_escaped_pointer_resolves(self, tmp_path: Path) -> None:
        operation = {"responses": {"200": {"description": "ok"}}}
        path = _write(
            tmp_path,
            _spec(
                paths={"/a/{id}": {"get": operation}},
                components={"x": {"$ref": "#/paths/~1a~1%7Bid%7D/get"}},
            ),
        )
        load_api_document(path, _JSON)

    def test_a_circular_chain_of_references_is_refused(self, tmp_path: Path) -> None:
        schemas = {"A": {"$ref": "#/components/schemas/B"}, "B": {"$ref": "#/components/schemas/A"}}
        problems = _problems(_write(tmp_path, _spec(components={"schemas": schemas})))
        assert problems[0] == (
            "has $ref '#/components/schemas/B' at /components/schemas/A that is circular: "
            "#/components/schemas/B → #/components/schemas/A → #/components/schemas/B"
        )

    def test_a_recursive_schema_is_ordinary(self, tmp_path: Path) -> None:
        """A tree node whose children are tree nodes refers to itself *inside*."""
        node = {
            "type": "object",
            "properties": {
                "children": {"type": "array", "items": {"$ref": "#/components/schemas/Node"}}
            },
        }
        path = _write(tmp_path, _spec(components={"schemas": {"Node": node}}))
        load_api_document(path, _JSON)

    def test_a_reference_in_sample_data_is_not_followed(self, tmp_path: Path) -> None:
        sample = {"$ref": "elsewhere.yaml"}
        schema = {
            "type": "object",
            "example": sample,
            "default": sample,
            "enum": [sample],
            "examples": [sample],
            "x-vendor": sample,
            # A property may be called anything, keywords included.
            "properties": {
                "$ref": {"type": "string"},
                "default": {"$ref": "#/components/schemas/S"},
            },
        }
        media = {"schema": schema, "examples": {"one": {"value": sample, "summary": "s"}}}
        document = _spec(
            paths={
                "/a": {
                    "get": {
                        "responses": {
                            "200": {"description": "ok", "content": {"application/json": media}}
                        }
                    }
                }
            },
            components={"schemas": {"S": {"type": "string"}}},
        )
        load_api_document(_write(tmp_path, document), _JSON)

    def test_a_property_named_like_a_keyword_is_still_checked(self, tmp_path: Path) -> None:
        schema = {"properties": {"default": {"$ref": "#/components/schemas/Missing"}}}
        path = _write(tmp_path, _spec(components={"schemas": {"S": schema}}))
        assert "names nothing" in _problems(path)[0]

    def test_a_component_named_like_a_keyword_is_still_checked(self, tmp_path: Path) -> None:
        schemas = {"example": {"$ref": "#/components/schemas/Missing"}}
        path = _write(tmp_path, _spec(components={"schemas": schemas}))
        assert _problems(path) == (
            "has $ref '#/components/schemas/Missing' at /components/schemas/example that "
            "names nothing in the file",
        )

    def test_many_problems_are_capped(self, tmp_path: Path) -> None:
        schemas = {f"S{i}": {"$ref": f"#/nothing/{i}"} for i in range(25)}
        problems = _problems(_write(tmp_path, _spec(components={"schemas": schemas})))
        assert len(problems) == ref_walk.MAX_PROBLEMS + 1
        assert problems[-1] == "…and 5 more $ref problems"


class TestBounds:
    def test_a_file_over_the_limit_is_refused_without_parsing(self, tmp_path: Path) -> None:
        path = tmp_path / "big.json"
        path.write_bytes(b" " * (MAX_API_FILE_BYTES + 1))
        assert _problems(path) == ("is larger than 5 MiB, the limit for an API file",)

    def test_an_alias_bomb_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ref_walk, "MAX_NODES", 10_000)
        lines = [
            "openapi: 3.0.3",
            "info: {title: T, version: '1'}",
            "paths: {}",
            "a0: &a0 [x, x, x, x, x, x, x, x, x, x]",
        ]
        lines += [f"a{i}: &a{i} [{', '.join([f'*a{i - 1}'] * 10)}]" for i in range(1, 6)]
        path = tmp_path / "bomb.yaml"
        path.write_text("\n".join(lines) + "\n")
        assert _problems(path, _YAML) == ("has more than 10,000 nodes once its aliases expand",)

    def test_an_alias_that_contains_itself_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "loop.yaml"
        path.write_text("openapi: 3.0.3\ninfo: {title: T, version: '1'}\npaths: {}\nx: &x [*x]\n")
        assert _problems(path, _YAML) == ("contains itself at /x/0 (a recursive YAML alias)",)

    def test_a_document_nested_too_deep_is_refused(self, tmp_path: Path) -> None:
        deep: Any = "leaf"
        for _ in range(ref_walk.MAX_DEPTH + 1):
            deep = {"a": deep}
        problems = _problems(_write(tmp_path, _spec(components=deep)))
        assert problems[0].startswith(
            f"nests deeper than {ref_walk.MAX_DEPTH} levels at /components"
        )

    def test_an_unreadable_file_is_reported(self, tmp_path: Path) -> None:
        assert _problems(tmp_path / "absent.json")[0].startswith("cannot be read:")


class TestCache:
    def test_a_second_load_of_the_same_bytes_is_the_same_document(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _spec())
        assert load_api_document(path, _JSON) is load_api_document(path, _JSON)

    def test_an_edited_file_is_parsed_again(self, tmp_path: Path) -> None:
        path = _write(tmp_path, _spec())
        first = load_api_document(path, _JSON)
        _write(tmp_path, _spec(info={"title": "Edited", "version": "2"}))
        second = load_api_document(path, _JSON)
        assert second is not first
        assert second.content["info"]["title"] == "Edited"

    def test_a_refused_file_is_not_cached(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"swagger": "2.0"})
        _problems(path)
        _write(tmp_path, _spec())
        assert load_api_document(path, _JSON).openapi == "3.0.3"

    def test_the_cache_is_bounded_by_the_bytes_it_holds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = _write(tmp_path, _spec(), "a.json")
        second = _write(tmp_path, _spec(), "b.json")
        monkeypatch.setattr(loader, "CACHE_BYTES", first.stat().st_size)
        kept = load_api_document(first, _JSON)
        load_api_document(second, _JSON)  # evicts the first: both do not fit
        assert load_api_document(first, _JSON) is not kept

    def test_the_cache_is_bounded_by_the_documents_it_holds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(loader, "CACHE_SIZE", 1)
        first, second = _write(tmp_path, _spec(), "a.json"), _write(tmp_path, _spec(), "b.json")
        kept = load_api_document(first, _JSON)
        load_api_document(second, _JSON)
        assert load_api_document(first, _JSON) is not kept

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

"""``env.apis`` at compile time: every API file is checked, packed and named (ADR-0030)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.paths import FIXTURES_DIR
from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.openapi import forget_api_documents

ICH = FIXTURES_DIR / "openapi" / "industry-core-hub.yaml"
_SOURCE = "industry-core-hub.yaml"


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    forget_api_documents()
    yield
    forget_api_documents()


def _tck(
    tmp_path: Path,
    apis: list[dict[str, Any]] | None = None,
    *,
    reference: str = "${{ env.apis.ich }}",
    variables: list[dict[str, Any]] | None = None,
) -> Path:
    """A TCK with the Industry Core Hub document under apis/ and one test reading it."""
    (tmp_path / "apis").mkdir(exist_ok=True)
    shutil.copy(ICH, tmp_path / "apis" / _SOURCE)
    (tmp_path / "tests").mkdir(exist_ok=True)
    test = {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "read-api",
        "namespace": "api-tck",
        "metadata": {"name": "Read the API file"},
        "execution": [
            {
                "id": "title",
                "uses": "util/json_path_extract",
                "with": {"input": reference, "path": "info.title"},
            }
        ],
    }
    (tmp_path / "tests" / "read-api.yaml").write_text(yaml.safe_dump(test))
    manifest = {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "api-tck",
        "metadata": {"name": "API TCK", "version": "1.0"},
        "env": {
            "variables": variables or [],
            "apis": [{"id": "ich", "source": _SOURCE}] if apis is None else apis,
        },
        "tests": [{"id": "read-api.yaml"}],
    }
    path = tmp_path / "index.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    return path


def _errors(manifest: Path) -> list[str]:
    return [
        issue.message for issue in Compiler().validate(manifest).issues if issue.level == "error"
    ]


class TestAValidApiFile:
    def test_it_validates(self, tmp_path: Path) -> None:
        assert _errors(_tck(tmp_path)) == []

    def test_it_is_compiled_into_the_ir_with_its_inferred_type(self, tmp_path: Path) -> None:
        manifest, execution = Compiler().compile_plain(_tck(tmp_path), tmp_path / "out")

        assert execution["apis"] == {
            "ich": {"asset_key": _SOURCE, "type": "application/vnd.oai.openapi"}
        }
        assert execution["global_symbols"]["env.apis.ich"] == {
            "source": "env.apis",
            "type": "object",
        }
        [asset] = manifest["assets"]["apis"]
        assert asset["path"] == f"assets/apis/{_SOURCE}"
        assert asset["mediaType"] == "application/vnd.oai.openapi"
        assert asset["size"] == ICH.stat().st_size
        assert (tmp_path / "out" / "assets" / "apis" / _SOURCE).read_bytes() == ICH.read_bytes()

    def test_a_declared_type_is_kept(self, tmp_path: Path) -> None:
        apis = [{"id": "ich", "source": _SOURCE, "type": "application/yaml"}]
        _, execution = Compiler().compile_plain(_tck(tmp_path, apis), tmp_path / "out")
        assert execution["apis"]["ich"]["type"] == "application/yaml"

    def test_the_package_checksum_covers_the_file(self, tmp_path: Path) -> None:
        first, _ = Compiler().compile_plain(_tck(tmp_path), tmp_path / "a")
        with (tmp_path / "apis" / _SOURCE).open("a") as handle:
            handle.write("\n# edited\n")
        second, _ = Compiler().compile_plain(_tck(tmp_path), tmp_path / "b")
        assert first["package"]["checksum"] != second["package"]["checksum"]


class TestARefusedApiFile:
    def _label(self, source: str = _SOURCE) -> str:
        return f"API file apis/{source} (env.apis[ich])"

    def test_a_missing_file(self, tmp_path: Path) -> None:
        manifest = _tck(tmp_path, [{"id": "ich", "source": "absent.yaml"}])
        assert f"{self._label('absent.yaml')} not found." in _errors(manifest)

    @pytest.mark.parametrize("source", ["../index.yaml", "/etc/passwd.yaml", "a\\b.yaml"])
    def test_a_file_outside_apis(self, tmp_path: Path, source: str) -> None:
        manifest = _tck(tmp_path, [{"id": "ich", "source": source}])
        assert any(
            error.startswith(f"{self._label(source)} must name a file inside apis/")
            for error in _errors(manifest)
        )

    def test_a_document_that_does_not_parse(self, tmp_path: Path) -> None:
        manifest = _tck(tmp_path)
        (tmp_path / "apis" / _SOURCE).write_text("openapi: [unclosed\n")
        assert any(
            error.startswith(f"{self._label()} is not valid YAML:") for error in _errors(manifest)
        )

    def test_a_json_type_on_a_yaml_file(self, tmp_path: Path) -> None:
        manifest = _tck(tmp_path, [{"id": "ich", "source": _SOURCE, "type": "application/json"}])
        assert any(
            error.startswith(f"{self._label()} is not valid JSON:") for error in _errors(manifest)
        )

    def test_a_swagger_2_document(self, tmp_path: Path) -> None:
        manifest = _tck(tmp_path)
        swagger = {"swagger": "2.0", "info": {"title": "T", "version": "1"}, "paths": {}}
        (tmp_path / "apis" / _SOURCE).write_text(yaml.safe_dump(swagger))
        assert (
            f"{self._label()} is Swagger 2.0, which is not supported; convert it to OpenAPI "
            "3.0 or 3.1 first (e.g. with swagger2openapi)."
        ) in _errors(manifest)

    def test_an_external_reference(self, tmp_path: Path) -> None:
        manifest = _tck(tmp_path)
        document = yaml.safe_load(ICH.read_text())
        document["components"]["schemas"]["Shared"] = {"$ref": "https://example.org/shared.yaml"}
        (tmp_path / "apis" / _SOURCE).write_text(json.dumps(document))
        assert (
            f"{self._label()} has $ref 'https://example.org/shared.yaml' at "
            "/components/schemas/Shared that points outside the file; an API file must be "
            "self-contained — bundle it into one file first."
        ) in _errors(manifest)

    def test_a_duplicate_id(self, tmp_path: Path) -> None:
        apis = [{"id": "ich", "source": _SOURCE}, {"id": "ich", "source": _SOURCE}]
        assert "env.apis: id 'ich' is declared 2 times; each API needs its own id." in _errors(
            _tck(tmp_path, apis)
        )

    def test_a_variable_called_apis(self, tmp_path: Path) -> None:
        variable = {
            "id": "apis",
            "uses": "variable/type/string",
            "with": {"value": "x"},
            "returns": {"value": {"type": "string"}},
        }
        errors = _errors(_tck(tmp_path, variables=[variable]))
        assert any(
            error.startswith("env.variables: a variable may not be called 'apis'")
            for error in errors
        )

    def test_a_type_that_is_not_an_api_type(self, tmp_path: Path) -> None:
        manifest = _tck(tmp_path, [{"id": "ich", "source": _SOURCE, "type": "text/plain"}])
        with pytest.raises(ValueError, match="application/vnd.oai.openapi"):
            _errors(manifest)


class TestReferences:
    def test_an_api_the_manifest_does_not_declare(self, tmp_path: Path) -> None:
        errors = _errors(_tck(tmp_path, reference="${{ env.apis.other }}"))
        assert any("'${{ env.apis.other }}' in param 'input' names nothing" in e for e in errors)

    def test_a_reference_into_the_document(self, tmp_path: Path) -> None:
        errors = _errors(_tck(tmp_path, reference="${{ env.apis.ich.info.title }}"))
        assert any(
            "'${{ env.apis.ich.info.title }}' reaches into API file 'ich'. A step is handed "
            "the whole document — write '${{ env.apis.ich }}'." in e
            for e in errors
        )

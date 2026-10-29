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

"""The labs API steps held to the API files they name, at compile time (ADR-0030 §5)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.paths import FIXTURES_DIR
from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.compiler.validation._api_steps import dataplane_providers
from tractusx_testlab.openapi import forget_api_documents

SHOP = FIXTURES_DIR / "openapi" / "shop-3.0.yaml"
API = "${{ env.apis.shop }}"


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    forget_api_documents()
    yield
    forget_api_documents()


def _issues(
    tmp_path: Path, steps: list[dict[str, Any]], extensions: list[str] | None = None
) -> list[tuple[str, str]]:
    (tmp_path / "apis").mkdir(exist_ok=True)
    shutil.copy(SHOP, tmp_path / "apis" / "shop.yaml")
    (tmp_path / "tests").mkdir(exist_ok=True)
    test = {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "api",
        "namespace": "api-tck",
        "metadata": {"name": "API"},
        "execution": steps,
    }
    (tmp_path / "tests" / "api.yaml").write_text(yaml.safe_dump(test))
    manifest = {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "api-tck",
        "metadata": {"name": "API TCK", "version": "1.0"},
        "extensions": ["labs"] if extensions is None else extensions,
        "env": {"apis": [{"id": "shop", "source": "shop.yaml"}]},
        "tests": [{"id": "api.yaml"}],
    }
    (tmp_path / "index.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return [
        (issue.level, issue.message)
        for issue in Compiler().validate(tmp_path / "index.yaml").issues
        if "experimental extension" not in issue.message or "does not enable" in issue.message
    ]


def _call(
    with_: dict[str, Any], uses: str = "labs/http/api_request", **extra: Any
) -> dict[str, Any]:
    return {"id": "call", "uses": uses, "with": {"api": API, **with_}, **extra}


def _errors(tmp_path: Path, *steps: dict[str, Any]) -> list[str]:
    return [message for level, message in _issues(tmp_path, list(steps)) if level == "error"]


def _warnings(tmp_path: Path, *steps: dict[str, Any]) -> list[str]:
    return [message for level, message in _issues(tmp_path, list(steps)) if level == "warning"]


class TestOperations:
    def test_a_documented_operation_with_its_parameters_compiles(self, tmp_path: Path) -> None:
        assert (
            _errors(tmp_path, _call({"operation": "getMaterial", "path_params": {"id": "m"}})) == []
        )

    def test_an_unknown_operation_is_refused_with_the_closest(self, tmp_path: Path) -> None:
        (error,) = _errors(tmp_path, _call({"operation": "getMaterials"}))
        assert "no operation 'getMaterials'" in error and "'getMaterial'" in error

    def test_method_and_path_name_an_operation_too(self, tmp_path: Path) -> None:
        assert (
            _errors(tmp_path, _call({"operation": "GET /materials", "query": {"limit": 1}})) == []
        )

    def test_a_missing_or_unknown_path_parameter_is_refused(self, tmp_path: Path) -> None:
        errors = _errors(
            tmp_path, _call({"operation": "getMaterial", "path_params": {"ident": "m"}})
        )
        assert len(errors) == 2
        assert any("no placeholder 'ident'" in e for e in errors)
        assert any("needs path parameter 'id'" in e for e in errors)

    def test_a_missing_required_query_parameter_or_body_is_refused(self, tmp_path: Path) -> None:
        assert (
            "needs query parameter 'limit'"
            in _errors(tmp_path, _call({"operation": "listMaterials"}))[0]
        )
        assert (
            "requires a request body"
            in _errors(tmp_path, _call({"operation": "createMaterial"}))[0]
        )

    def test_values_given_by_reference_are_not_second_guessed(self, tmp_path: Path) -> None:
        step = _call({"operation": "listMaterials", "query": "${{ env.query }}"})
        assert not [e for e in _errors(tmp_path, step) if "query parameter" in e]

    def test_api_must_name_an_api_file(self, tmp_path: Path) -> None:
        step = {
            "id": "call",
            "uses": "labs/http/api_request",
            "with": {"api": "shop", "operation": "health"},
        }
        assert any("'${{ env.apis.<id> }}'" in e for e in _errors(tmp_path, step))

    def test_the_labs_steps_need_the_labs_extension(self, tmp_path: Path) -> None:
        issues = _issues(tmp_path, [_call({"operation": "health"})], extensions=[])
        assert any("does not enable" in message for _, message in issues)


class TestSweep:
    def test_unknown_operations_and_methods_are_refused_and_unknown_tags_warned(
        self, tmp_path: Path
    ) -> None:
        step = _call(
            {"operations": ["nope"], "methods": ["FETCH"], "tags": ["ghost"]}, "labs/http/api_sweep"
        )
        issues = _issues(tmp_path, [step])
        assert {level for level, m in issues if "no operation 'nope'" in m} == {"error"}
        assert {level for level, m in issues if "FETCH" in m} == {"error"}
        assert {level for level, m in issues if "'ghost'" in m} == {"warning"}


class TestDataplane:
    def test_the_providers_are_read_off_the_contracts(self) -> None:
        assert {
            "connector/consumer/pull_data_filtered",
            "connector/consumer/do_dsp",
            "connector/consumer/get_edr",
        } <= dataplane_providers()
        assert "http/http_request" not in dataplane_providers()

    def test_a_call_with_no_earlier_provider_is_warned(self, tmp_path: Path) -> None:
        step = _call({"operation": "health"}, "labs/connector/dataplane/api_request")
        assert any("no earlier step publishes" in w for w in _warnings(tmp_path, step))

    def test_a_call_after_a_provider_is_not_warned(self, tmp_path: Path) -> None:
        pull = {
            "id": "pull",
            "uses": "connector/consumer/pull_data_filtered",
            "with": {"filters": [{"operand_left": "id", "operand_right": "a"}]},
        }
        step = _call({"operation": "health"}, "labs/connector/dataplane/api_request")
        assert not [w for w in _warnings(tmp_path, pull, step) if "no earlier step" in w]

    def test_a_call_given_both_values_is_not_warned(self, tmp_path: Path) -> None:
        step = _call(
            {"operation": "health", "dataplane_url": "https://dp", "edr_token": ""},
            "labs/connector/dataplane/api_request",
        )
        assert not [w for w in _warnings(tmp_path, step) if "no earlier step" in w]


class TestResponseCheck:
    def test_under_a_call_it_needs_no_input(self, tmp_path: Path) -> None:
        step = _call({"operation": "health"}, validate=[{"uses": "labs/validate/api_response"}])
        assert _errors(tmp_path, step) == []

    def test_under_another_step_it_needs_api_and_operation(self, tmp_path: Path) -> None:
        step = {
            "id": "plain",
            "uses": "http/http_request",
            "with": {"url": "https://x"},
            "validate": [{"uses": "labs/validate/api_response", "with": {"input": "value"}}],
        }
        assert any("needs 'api' and 'operation'" in e for e in _errors(tmp_path, step))

    def test_a_named_operation_is_checked_against_the_document(self, tmp_path: Path) -> None:
        step = _call(
            {"operation": "health"},
            validate=[
                {"uses": "labs/validate/api_response", "with": {"api": API, "operation": "helth"}}
            ],
        )
        assert any("no operation 'helth'" in e for e in _errors(tmp_path, step))

    def test_the_labs_check_needs_the_labs_extension(self, tmp_path: Path) -> None:
        step = {
            "id": "plain",
            "uses": "util/generate_uuid",
            "validate": [
                {"uses": "labs/validate/api_response", "with": {"api": API, "operation": "health"}}
            ],
        }
        issues = _issues(tmp_path, [step], extensions=[])
        assert any("The check 'labs/validate/api_response'" in m for _, m in issues)

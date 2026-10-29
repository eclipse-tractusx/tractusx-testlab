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

"""``${{ env.apis.<id> }}`` at run time: the parsed document, read-only, as data (ADR-0030)."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.paths import FIXTURES_DIR
from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.models import UnresolvedReferenceError
from tractusx_testlab.models.authoring import ApiDefinition, EnvDefinition
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition
from tractusx_testlab.openapi import FrozenDict, forget_api_documents
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.loading.resolver import resolve_params

ICH = FIXTURES_DIR / "openapi" / "industry-core-hub.yaml"


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    forget_api_documents()
    yield
    forget_api_documents()


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _tck(base_dir: Path, source: str = "ich.yaml") -> Tck:
    definition = TckDefinition(
        kind="tck",
        syntax="v1-alpha",
        id="api-tck",
        metadata=TckMetadataDefinition(name="API TCK", version="1.0.0"),
        env=EnvDefinition(apis=[ApiDefinition(id="ich", source=source)]),
        tests=[],
    )
    return Tck(definition, base_dir=base_dir)


def _place(root: Path, layout: str, text: str | None = None) -> None:
    folder = (root / layout if layout else root) / "apis"
    folder.mkdir(parents=True)
    if text is None:
        shutil.copy(ICH, folder / "ich.yaml")
    else:
        (folder / "ich.yaml").write_text(text)


@pytest.mark.parametrize("layout", ["", "assets"], ids=["raw", "compiled"])
def test_the_document_is_bound_read_only(context: StepContext, tmp_path: Path, layout: str) -> None:
    _place(tmp_path, layout)
    seed_context_variables(context, _tck(tmp_path), None)

    document = context.get_variable("apis.ich")
    assert isinstance(document, FrozenDict)
    assert document["info"]["title"] == "Industry Core Hub Backend API"
    with pytest.raises(TypeError, match="read-only"):
        document["paths"].clear()


def test_it_is_bound_once_under_the_name_the_reference_reads(
    context: StepContext, tmp_path: Path
) -> None:
    _place(tmp_path, "")
    seed_context_variables(context, _tck(tmp_path), None)
    assert [name for name in context.variables if "ich" in name] == ["apis.ich"]
    assert not context.is_template("apis.ich")


def test_a_reference_resolves_to_the_document_itself(context: StepContext, tmp_path: Path) -> None:
    _place(tmp_path, "assets")
    seed_context_variables(context, _tck(tmp_path), None)

    resolved = resolve_params({"api": "${{ env.apis.ich }}"}, context)

    assert resolved["api"] is context.get_variable("apis.ich")


def test_the_document_is_data_not_a_template(context: StepContext, tmp_path: Path) -> None:
    """A ``${{`` in somebody else's description is text, not the author's reference."""
    _place(
        tmp_path,
        "",
        "openapi: 3.0.3\ninfo: {title: 'Uses ${{ env.secret }}', version: '1'}\npaths: {}\n",
    )
    seed_context_variables(context, _tck(tmp_path), None)

    resolved = resolve_params({"api": "${{ env.apis.ich }}"}, context)

    assert resolved["api"]["info"]["title"] == "Uses ${{ env.secret }}"


def test_a_refused_file_is_logged_and_left_unbound(
    context: StepContext, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _place(tmp_path, "", "swagger: '2.0'\n")
    with caplog.at_level(logging.ERROR):
        seed_context_variables(context, _tck(tmp_path), None)

    assert "API file apis/ich.yaml (env.apis[ich]) is Swagger 2.0" in caplog.text
    with pytest.raises(UnresolvedReferenceError):
        resolve_params({"api": "${{ env.apis.ich }}"}, context)


def test_a_file_missing_from_the_package_is_logged(
    context: StepContext, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        seed_context_variables(context, _tck(tmp_path), None)
    assert "(env.apis[ich]) is not in the package" in caplog.text


def test_a_source_leaving_the_package_is_refused(context: StepContext, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'..' segment"):
        seed_context_variables(context, _tck(tmp_path, "../../etc/passwd.yaml"), None)

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Tests for env.schemas/env.testdata asset seeding and JSON Schema validation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure all built-in steps are registered
from tractusx_testlab.models.authoring.definitions import (
    EnvDefinition,
    SchemaDefinition,
    TckDefinition,
    TckMetadataDefinition,
)
from tractusx_testlab.models.authoring.definitions import (
    TestDataDefinition as _TestDataDefinition,  # aliased: pytest collects Test* classes
)
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.loading.resolver import resolve_params
from tractusx_testlab.scripting.script import Tck
from tractusx_testlab.steps._checks.schema import check_schema_validation

_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["holder"],
    "properties": {"holder": {"type": "string"}},
}
_TESTDATA = {"header": {"messageId": "urn:uuid:abc"}}


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _make_tck(base_dir: Path) -> Tck:
    definition = TckDefinition(
        kind="tck",
        syntax="v1-alpha",
        id="asset-tck",
        metadata=TckMetadataDefinition(name="Asset TCK", version="1.0.0"),
        env=EnvDefinition(
            schemas=[SchemaDefinition(id="cert_schema", source="cert.json")],
            testdata=[_TestDataDefinition(id="body", source="body.json")],
        ),
        tests=[],
    )
    return Tck(definition, base_dir=base_dir)


def _write_assets(root: Path, folder_prefix: str) -> None:
    """Write the schema/testdata pair under *folder_prefix* (``""`` or ``assets``)."""
    base = root / folder_prefix if folder_prefix else root
    (base / "schemas").mkdir(parents=True)
    (base / "testdata").mkdir(parents=True)
    (base / "schemas" / "cert.json").write_text(json.dumps(_SCHEMA), encoding="utf-8")
    (base / "testdata" / "body.json").write_text(json.dumps(_TESTDATA), encoding="utf-8")


class TestAssetSeeding:
    """env.schemas and env.testdata must be seeded for both package layouts."""

    @pytest.mark.parametrize("layout", ["", "assets"], ids=["raw", "compiled"])
    def test_schemas_are_seeded(
        self,
        context: StepContext,
        tmp_path: Path,
        layout: str,
    ) -> None:
        _write_assets(tmp_path, layout)
        seed_context_variables(context, _make_tck(tmp_path), None)

        assert context.get_variable("schemas.cert_schema") == _SCHEMA
        assert context.get_variable("env.schemas.cert_schema") == _SCHEMA

    @pytest.mark.parametrize("layout", ["", "assets"], ids=["raw", "compiled"])
    def test_testdata_is_seeded(
        self,
        context: StepContext,
        tmp_path: Path,
        layout: str,
    ) -> None:
        _write_assets(tmp_path, layout)
        seed_context_variables(context, _make_tck(tmp_path), None)

        assert context.get_variable("testdata.body") == _TESTDATA
        assert context.get_variable("env.testdata.body") == _TESTDATA

    def test_missing_asset_is_skipped_without_raising(
        self,
        context: StepContext,
        tmp_path: Path,
    ) -> None:
        seed_context_variables(context, _make_tck(tmp_path), None)

        assert context.get_variable("schemas.cert_schema") is None

    def test_schema_reference_resolves_in_step_params(
        self,
        context: StepContext,
        tmp_path: Path,
    ) -> None:
        _write_assets(tmp_path, "assets")
        seed_context_variables(context, _make_tck(tmp_path), None)

        resolved = resolve_params({"schema": "${{ env.schemas.cert_schema }}"}, context)

        assert resolved["schema"] == _SCHEMA


class TestSchemaValidation:
    """``validate/schema`` must perform real JSON Schema validation (ADR-0010).

    Exercised through :func:`check_schema_validation`, which is the code an
    assertion block actually reaches.  It used to be tested through a
    ``validate/schema`` *step* class — but the compiler rejects
    ``uses: validate/*`` as a step, so that class was unreachable from any TCK
    and the test was proving a path no author could take.  The step is gone; the
    stronger checks it carried moved into this function.
    """

    def test_valid_payload_passes(self) -> None:
        passed, message = check_schema_validation({"holder": "BPNL000000000000"}, _SCHEMA)
        assert passed, message

    def test_missing_required_property_fails(self) -> None:
        passed, message = check_schema_validation({}, _SCHEMA)
        assert not passed
        assert "'holder' is a required property" in message

    def test_wrong_type_fails(self) -> None:
        passed, message = check_schema_validation({"holder": 42}, _SCHEMA)
        assert not passed
        assert "Schema validation failed" in message

    def test_json_string_payload_is_decoded(self) -> None:
        passed, message = check_schema_validation(json.dumps({"holder": "BPNL1"}), _SCHEMA)
        assert passed, message

    def test_unresolved_schema_reference_is_named_as_such(self) -> None:
        passed, message = check_schema_validation({}, "${{ env.schemas.missing }}")
        assert not passed
        assert "not valid JSON" in message

    def test_a_missing_schema_is_refused(self) -> None:
        passed, message = check_schema_validation({}, None)
        assert not passed
        assert "No schema provided" in message

    def test_an_invalid_schema_is_refused_rather_than_accepting_everything(self) -> None:
        """A malformed schema must fail loudly, not validate nothing successfully."""
        passed, message = check_schema_validation({"anything": 1}, {"type": "nonsense"})
        assert not passed
        assert "Invalid JSON Schema" in message

    def test_every_error_is_reported_not_only_the_first(self) -> None:
        """A payload wrong in two places costs one run to diagnose, not two."""
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "required": ["a", "b"],
        }
        passed, message = check_schema_validation({"a": 1, "b": 2}, schema)
        assert not passed
        assert "2 error(s)" in message
        assert "a:" in message
        assert "b:" in message

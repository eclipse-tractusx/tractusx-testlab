#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Tests for Pydantic definition models (V2: StepDefinitionV2, ScriptDefinitionV2, etc.)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tractusx_testlab.models.authoring.definitions import (
    AssertionV2,
    MetadataDefinition,
    ScriptDefinitionV2,
    ServiceDefinition,
    StepDefinitionV2,
    TckDefinitionV2,
    TckMetadataDefinition,
    TckTestEntry,
    VariableDefinition,
)
from tractusx_testlab.models.primitives.enums import (
    FailurePolicy,
    ServiceType,
)


class TestStepDefinitionV2:
    """Tests for StepDefinitionV2 model validation."""

    def test_minimal_step_only_requires_uses(self) -> None:
        step = StepDefinitionV2(uses="connector/provider/create_asset")
        assert step.uses == "connector/provider/create_asset"
        assert step.with_ is None
        assert (step.validate or []) == []

    def test_step_with_all_fields(self) -> None:
        step = StepDefinitionV2(
            uses="http/http_request",
            name="Call API",
            description="Calls an external API",
            **{"with": {"url": "http://example.com"}},
            on_failure=FailurePolicy.CONTINUE,
            timeout_s=30.0,
        )
        assert step.name == "Call API"
        assert step.on_failure == FailurePolicy.CONTINUE
        assert step.timeout_s == 30.0

    def test_step_default_failure_policy_is_abort(self) -> None:
        step = StepDefinitionV2(uses="any_step")
        assert step.on_failure == FailurePolicy.ABORT

    def test_step_with_assertions(self) -> None:
        step = StepDefinitionV2(
            uses="http/http_request",
            validate=[
                AssertionV2(uses="assert/status_code", **{"with": {"value": 200}}),
                AssertionV2(uses="assert/not_null", **{"with": {"output": "body"}}),
            ],
        )
        assert len(step.validate) == 2
        assert step.validate[0].uses == "assert/status_code"


class TestScriptDefinitionV2:
    """Tests for ScriptDefinitionV2 model validation."""

    def test_minimal_script(self) -> None:
        script = ScriptDefinitionV2(
            syntax="v2",
            id="my-test-id",
            namespace="my-ns",
            metadata=MetadataDefinition(name="My Test"),
            execution=[],
        )
        assert script.metadata.name == "My Test"
        assert script.syntax == "v2"

    def test_script_with_steps(self) -> None:
        script = ScriptDefinitionV2(
            syntax="v2",
            id="s1",
            namespace="ns",
            metadata=MetadataDefinition(name="With Steps"),
            execution=[StepDefinitionV2(uses="connector/provider/create_asset")],
        )
        assert len(script.execution) == 1

    def test_script_all_phases(self) -> None:
        script = ScriptDefinitionV2(
            syntax="v2",
            id="full",
            namespace="ns",
            metadata=MetadataDefinition(name="Full"),
            setup=[StepDefinitionV2(uses="connector/provider/create_asset")],
            execution=[StepDefinitionV2(uses="http/http_request")],
            teardown=[StepDefinitionV2(uses="connector/provider/delete_asset")],
        )
        assert len(script.setup) == 1
        assert len(script.execution) == 1
        assert len(script.teardown) == 1

    def test_script_missing_metadata_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScriptDefinitionV2(syntax="v2", id="x", namespace="ns")  # type: ignore[call-arg]


class TestServiceDefinition:
    """Tests for ServiceDefinition model validation."""

    def test_service_requires_name_type_url(self) -> None:
        svc = ServiceDefinition(
            name="consumer",
            type=ServiceType.CONNECTOR_CONSUMER,
            base_url="http://localhost:9090",
        )
        assert svc.name == "consumer"
        assert svc.type == ServiceType.CONNECTOR_CONSUMER

    def test_service_missing_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            ServiceDefinition(name="bad")  # type: ignore[call-arg]


class TestTckDefinitionV2:
    """Tests for TckDefinitionV2 model."""

    def test_tck_minimal(self) -> None:
        tck = TckDefinitionV2(
            syntax="v2",
            id="ccm-tck",
            metadata=TckMetadataDefinition(name="CCM TCK"),
            tests=[TckTestEntry(id="test.yaml")],
        )
        assert tck.metadata.name == "CCM TCK"
        assert tck.syntax == "v2"

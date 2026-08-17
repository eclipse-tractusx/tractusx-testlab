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

"""Tests for Pydantic definition models (StepDefinition, ScriptDefinition, etc.)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tractusx_testlab.models.authoring.definitions import (
    Assertion,
    MetadataDefinition,
    ScriptDefinition,
    ServiceDefinition,
    StepDefinition,
    TckDefinition,
    TckMetadataDefinition,
    TckTestEntry,
)
from tractusx_testlab.models.primitives.enums import (
    ServiceType,
)


class TestStepDefinition:
    """Tests for StepDefinition model validation."""

    def test_minimal_step_only_requires_uses(self) -> None:
        step = StepDefinition(uses="connector/provider/create_asset")
        assert step.uses == "connector/provider/create_asset"
        assert step.with_ is None
        assert (step.validate or []) == []

    def test_step_with_all_fields(self) -> None:
        step = StepDefinition(
            uses="http/http_request",
            name="Call API",
            description="Calls an external API",
            **{"with": {"url": "http://example.com"}},
            timeout_s=30.0,
        )
        assert step.name == "Call API"
        assert step.timeout_s == 30.0

    def test_step_with_assertions(self) -> None:
        step = StepDefinition(
            uses="http/http_request",
            validate=[
                Assertion(uses="validate/assert/equals", **{"with": {"input": "status_code", "value": 200}}),
                Assertion(uses="validate/assert", **{"with": {"input": "response_body", "operator": "not_null"}}),
            ],
        )
        assert len(step.validate) == 2
        assert step.validate[0].uses == "validate/assert/equals"


class TestScriptDefinition:
    """Tests for ScriptDefinition model validation."""

    def test_minimal_script(self) -> None:
        script = ScriptDefinition(
            syntax="v1-alpha",
            id="my-test-id",
            namespace="my-ns",
            metadata=MetadataDefinition(name="My Test"),
            execution=[],
        )
        assert script.metadata.name == "My Test"
        assert script.syntax == "v1-alpha"

    def test_script_with_steps(self) -> None:
        script = ScriptDefinition(
            syntax="v1-alpha",
            id="s1",
            namespace="ns",
            metadata=MetadataDefinition(name="With Steps"),
            execution=[StepDefinition(uses="connector/provider/create_asset")],
        )
        assert len(script.execution) == 1

    def test_script_all_phases(self) -> None:
        script = ScriptDefinition(
            syntax="v1-alpha",
            id="full",
            namespace="ns",
            metadata=MetadataDefinition(name="Full"),
            setup=[StepDefinition(uses="connector/provider/create_asset")],
            execution=[StepDefinition(uses="http/http_request")],
            teardown=[StepDefinition(uses="connector/provider/delete_asset")],
        )
        assert len(script.setup) == 1
        assert len(script.execution) == 1
        assert len(script.teardown) == 1

    def test_script_missing_metadata_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScriptDefinition(syntax="v1-alpha", id="x", namespace="ns")  # type: ignore[call-arg]


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


class TestTckDefinition:
    """Tests for TckDefinition model."""

    def test_tck_minimal(self) -> None:
        tck = TckDefinition(
            syntax="v1-alpha",
            id="ccm-tck",
            metadata=TckMetadataDefinition(name="CCM TCK"),
            tests=[TckTestEntry(id="test.yaml")],
        )
        assert tck.metadata.name == "CCM TCK"
        assert tck.syntax == "v1-alpha"

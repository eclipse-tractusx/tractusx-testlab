###############################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Integration tests: CCM YAML parsing, index, assertions, registry, and services."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import tractusx_testlab.steps  # noqa: F401 — trigger @step registrations
from tractusx_testlab.compiler.validation._expressions import resolve_expression
from tractusx_testlab.models.authoring.definitions import AssertionV2, ServiceDefinition
from tractusx_testlab.models.authoring.infrastructure import DataspaceContext
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.scripting import StepRegistry
from tractusx_testlab.scripting.parser import YamlParser

CCM_DIR = Path(__file__).resolve().parent.parent / "docs" / "examples" / "certificate-management-v2" / "raw"
CCM_TESTS_DIR = CCM_DIR / "tests"

_CCM_TEST_FILES = {
    "available_notification.yaml": 4,
    "catalog_policy_validation.yaml": 1,
    "certificate_asset_validation.yaml": 1,
    "error_handling.yaml": 4,
    "expose_testlab_asset.yaml": 4,
    "push_certificate.yaml": 4,
    "request_certificate.yaml": 3,
    "send_feedback.yaml": 4,
    "validate_payload.yaml": 2,
}

_CCM_STEP_TYPES = [
    "create_asset", "create_contract_definition", "create_policy",
    "delete_asset", "delete_policy",
    "export_variable", "generate_uuid", "http_call_dataplane",
    "import_variable", "load_schema", "mock_endpoint",
    "pull_data_filtered", "query_catalog_with_filters",
    "wait_for_call",
]

_CCM_STEP_TYPES_UNREGISTERED: list[str] = []


class TestCcmYamlParsing:
    @pytest.mark.parametrize("filename,expected_steps", list(_CCM_TEST_FILES.items()))
    def test_ccm_yaml_parses_successfully(self, filename: str, expected_steps: int) -> None:

        yaml_path = CCM_TESTS_DIR / filename
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        raw_steps = data.get("execution", [])

        assert len(raw_steps) == expected_steps, (
            f"{filename}: expected {expected_steps} steps, got {len(raw_steps)}"
        )
        assert data.get("kind", "test") == "test", f"{filename} kind should be 'test'"
        for i, step_raw in enumerate(raw_steps):
            assert "uses" in step_raw or "type" in step_raw, (
                f"Step {i} in {filename} must declare a 'uses' verb or legacy 'type'"
            )

    @pytest.mark.parametrize("filename,expected_steps", list(_CCM_TEST_FILES.items()))
    def test_ccm_yaml_parses_into_script_definition(self, filename: str, expected_steps: int) -> None:

        script = YamlParser.parse_script(CCM_TESTS_DIR / filename)

        assert script is not None, f"{filename} did not parse into a ScriptDefinition"
        assert len(script.execution) == expected_steps, (
            f"{filename}: parser produced {len(script.execution)} steps, expected {expected_steps}"
        )


class TestCcmIndexParsing:
    def test_ccm_index_parses_as_tck(self) -> None:

        index_path = CCM_DIR / "index.yaml"
        with open(index_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["kind"] == "tck"
        assert data["id"] == "certificate-management-tck"
        tests = data.get("tests", [])
        assert len(tests) == 9, f"Expected 9 tests, got {len(tests)}"
        for entry in tests:
            assert "id" in entry, f"Each test entry must have an 'id' key, got {entry}"


class TestCompactAssertionParsing:
    """V2 AssertionV2 model construction with uses + with parameters."""

    def test_not_null_assertion_sets_uses_and_output(self) -> None:

        assertion = AssertionV2(uses="assert/not_null", **{"with": {"output": "body.certificateId"}})

        assert assertion.uses == "assert/not_null"
        assert (assertion.with_ or {}).get("output") == "body.certificateId"

    def test_equals_assertion_sets_uses_value_and_output(self) -> None:

        assertion = AssertionV2(uses="assert/equals", **{"with": {"output": "status", "value": 200}})

        assert assertion.uses == "assert/equals"
        assert (assertion.with_ or {}).get("value") == 200
        assert (assertion.with_ or {}).get("output") == "status"


class TestCcmServiceParsing:
    """ServiceDefinition model construction from inline service data."""

    def test_service_type_edc_connector_saturn_accepted(self) -> None:

        service = ServiceDefinition(
            name="provider_edc",
            type=ServiceType.EDC_CONNECTOR_SATURN,
            base_url="https://provider:8080",
        )

        assert service.name == "provider_edc"
        assert service.type == ServiceType.EDC_CONNECTOR_SATURN


class TestCcmInfrastructure:
    """The migrated CCM index carries the ADR-0019 dataspace and infrastructure blocks."""

    def test_ccm_index_dataspace_block_parses(self) -> None:

        tck = YamlParser.parse_tck(CCM_DIR / "index.yaml")

        assert tck.dataspace == DataspaceContext(ecosystem="Catena-X", version="saturn")

    def test_ccm_index_infrastructure_declares_engine_and_sut_connector(self) -> None:

        tck = YamlParser.parse_tck(CCM_DIR / "index.yaml")

        assert tck.infrastructure.engine["connector"].required is True
        assert tck.infrastructure.sut["connector"].required is True

    def test_setup_artifact_reference_resolves_to_canonical_ref(self) -> None:

        result = resolve_expression("${{ setup.ccm_policy.policy }}")

        assert result == {"$ref": "setup.ccm_policy.policy"}

    def test_sut_connector_reference_in_example_resolves_verbatim(self) -> None:

        with open(CCM_TESTS_DIR / "request_certificate.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        sut_ref = data["execution"][0]["with"]["counter_party_address"]

        result = resolve_expression(sut_ref)

        assert result == {"$ref": "infrastructure.sut.connector.counter_party_address"}


class TestCcmStepRegistry:
    @pytest.mark.parametrize("step_type", _CCM_STEP_TYPES)
    def test_ccm_step_types_all_registered(self, step_type: str) -> None:

        step_cls = StepRegistry.get(step_type, "saturn")

        assert step_cls is not None, f"Step type '{step_type}' is not registered for dataspace 'saturn'"

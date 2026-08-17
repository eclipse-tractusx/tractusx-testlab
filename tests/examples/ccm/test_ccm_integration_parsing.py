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

import pytest
import yaml

from tests.paths import CCM_RAW_DIR
from tractusx_testlab.compiler.validation._expressions import resolve_expression
from tractusx_testlab.models.authoring.definitions import Assertion, ServiceDefinition
from tractusx_testlab.models.authoring.infrastructure import DataspaceContext
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.scripting import StepRegistry
from tractusx_testlab.scripting.parser import YamlParser

CCM_TESTS_DIR = CCM_RAW_DIR / "tests"

#: The example's own test files, read from disk rather than listed here.
#: A hard-coded list drifts silently every time the example is reworked, and
#: has done so twice; what this suite is for is that the shipped example still
#: parses, not that it still has the shape someone wrote down once.
_CCM_TEST_FILES = sorted(path.name for path in CCM_TESTS_DIR.glob("*.yaml"))

_CCM_STEP_TYPES = [
    "connector/provider/create_asset", "connector/provider/create_contract_definition",
    "connector/provider/create_policy", "connector/provider/delete_asset",
    "connector/provider/delete_policy", "util/generate_uuid",
    "connector/dataplane/http_request", "mock/api",
    "connector/consumer/pull_data_filtered", "connector/consumer/query_catalog_with_filters",
    "mock/wait/http_request",
]

_CCM_STEP_TYPES_UNREGISTERED: list[str] = []


class TestCcmYamlParsing:
    def test_the_example_ships_test_files(self) -> None:
        """An empty glob would make every test below pass by doing nothing."""
        assert _CCM_TEST_FILES

    @pytest.mark.parametrize("filename", _CCM_TEST_FILES)
    def test_every_step_declares_what_it_uses(self, filename: str) -> None:

        data = yaml.safe_load((CCM_TESTS_DIR / filename).read_text(encoding="utf-8"))

        assert data.get("kind", "test") == "test", f"{filename} kind should be 'test'"
        raw_steps = data.get("execution", [])
        assert raw_steps, f"{filename} declares no execution steps"
        for i, step_raw in enumerate(raw_steps):
            assert "uses" in step_raw, f"Step {i} in {filename} must declare a 'uses' verb"

    @pytest.mark.parametrize("filename", _CCM_TEST_FILES)
    def test_ccm_yaml_parses_into_script_definition(self, filename: str) -> None:

        script = YamlParser.parse_script(CCM_TESTS_DIR / filename)
        raw = yaml.safe_load((CCM_TESTS_DIR / filename).read_text(encoding="utf-8"))

        assert script is not None, f"{filename} did not parse into a ScriptDefinition"
        assert len(script.execution) == len(raw["execution"]), (
            f"{filename}: the parser dropped steps the file declares"
        )

    @pytest.mark.parametrize("filename", _CCM_TEST_FILES)
    def test_every_step_the_example_uses_is_registered(self, filename: str) -> None:
        """The shipped example must not name a step the engine no longer has."""
        script = YamlParser.parse_script(CCM_TESTS_DIR / filename)

        unregistered = [
            step.uses
            for step in (*script.setup, *script.execution, *script.teardown)
            if StepRegistry.get(step.uses, script.dataspace_version) is None
        ]
        assert unregistered == []


class TestCcmIndexParsing:
    def test_ccm_index_parses_as_tck(self) -> None:

        index_path = CCM_RAW_DIR / "index.yaml"
        with open(index_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["kind"] == "tck"
        tests = data.get("tests", [])
        assert len(tests) == len(_CCM_TEST_FILES), (
            "the index and the tests/ directory disagree on how many tests there are"
        )
        for entry in tests:
            assert "id" in entry, f"Each test entry must have an 'id' key, got {entry}"


class TestCompactAssertionParsing:
    """Assertion model construction with uses + with parameters."""

    def test_not_null_assertion_sets_uses_and_output(self) -> None:

        assertion = Assertion(
            uses="validate/field",
            **{"with": {"input": "response_body", "path": "certificateId", "operator": "not_null"}},
        )

        assert assertion.uses == "validate/field"
        assert (assertion.with_ or {}).get("path") == "certificateId"

    def test_equals_assertion_sets_uses_value_and_output(self) -> None:

        assertion = Assertion(
            uses="validate/assert/equals",
            **{"with": {"input": "status_code", "value": 200}},
        )

        assert assertion.uses == "validate/assert/equals"
        assert (assertion.with_ or {}).get("value") == 200
        assert (assertion.with_ or {}).get("input") == "status_code"


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

        tck = YamlParser.parse_tck(CCM_RAW_DIR / "index.yaml")

        assert tck.dataspace == DataspaceContext(ecosystem="Catena-X", version="saturn")

    def test_ccm_index_infrastructure_declares_engine_and_sut_connector(self) -> None:

        tck = YamlParser.parse_tck(CCM_RAW_DIR / "index.yaml")

        assert tck.infrastructure.engine["connector"].required is True
        assert tck.infrastructure.sut["connector"].required is True

    def test_setup_artifact_reference_resolves_to_canonical_ref(self) -> None:

        result = resolve_expression("${{ setup.ccm_policy.policy }}")

        assert result == {"$ref": "setup.ccm_policy.policy"}

    def test_sut_connector_reference_in_example_resolves_verbatim(self) -> None:

        data = yaml.safe_load(
            (CCM_TESTS_DIR / "request_certificate.yaml").read_text(encoding="utf-8")
        )
        sut_ref = data["execution"][0]["with"]["counter_party_address"]

        result = resolve_expression(sut_ref)

        assert result == {"$ref": sut_ref.strip("${} ")}


class TestCcmStepRegistry:
    @pytest.mark.parametrize("step_type", _CCM_STEP_TYPES)
    def test_ccm_step_types_all_registered(self, step_type: str) -> None:

        step_cls = StepRegistry.get(step_type, "saturn")

        assert step_cls is not None, f"Step type '{step_type}' is not registered for dataspace 'saturn'"

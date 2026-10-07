###############################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Contributors to the Eclipse Foundation
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

"""Unit tests for Tck.infrastructure_requirements() and the underlying merge helper."""

from __future__ import annotations

from tests.paths import CCM_RAW_DIR
from tractusx_testlab.authoring.test import Tck, Test
from tractusx_testlab.models.authoring.definitions import (
    MetadataDefinition,
    TckDefinition,
    TckMetadataDefinition,
    TestDefinition,
)
from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    InfrastructureConfig,
    Standard,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tck(infrastructure: InfrastructureConfig | None = None) -> Tck:
    tck_def = TckDefinition(
        syntax="v1-alpha",
        id="test-tck",
        metadata=TckMetadataDefinition(name="Test TCK"),
        tests=[],
        infrastructure=infrastructure,
    )
    return Tck(tck_def)


def _make_test(infrastructure: InfrastructureConfig | None = None) -> Test:
    test_def = TestDefinition(
        syntax="v1-alpha",
        id="test",
        namespace="test.ns",
        metadata=MetadataDefinition(name="Test Test"),
        infrastructure=infrastructure,
    )
    return Test(test_def)


def _req(required: bool, standard: Standard | None = None) -> CapabilityRequirement:
    return CapabilityRequirement(required=required, standard=standard)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInfrastructureRequirementsTckLevel:
    def test_tck_level_infrastructure_is_returned_directly(self) -> None:
        infra = InfrastructureConfig(
            engine={"connector": _req(True)},
            sut={"connector": _req(True), "dtr": _req(False)},
        )
        tck = _make_tck(infrastructure=infra)

        result = tck.infrastructure_requirements()

        assert result is infra

    def test_tck_level_takes_priority_over_test_level(self) -> None:
        tck_infra = InfrastructureConfig(engine={"connector": _req(True)})
        tck = _make_tck(infrastructure=tck_infra)
        test = _make_test(infrastructure=InfrastructureConfig(sut={"dtr": _req(True)}))
        tck._tests = [test]

        result = tck.infrastructure_requirements()

        assert result is tck_infra
        assert "dtr" not in result.sut


class TestInfrastructureRequirementsEmpty:
    def test_no_infrastructure_declared_returns_empty_config(self) -> None:
        tck = _make_tck()

        result = tck.infrastructure_requirements()

        assert isinstance(result, InfrastructureConfig)
        assert result.engine == {}
        assert result.sut == {}

    def test_with_no_infrastructure_produces_empty_config(self) -> None:
        tck = _make_tck()
        tck._tests = [_make_test()]

        result = tck.infrastructure_requirements()

        assert result.engine == {}
        assert result.sut == {}


class TestInfrastructureRequirementsTestMerge:
    def test_single_test_infrastructure_is_returned(self) -> None:
        test = _make_test(
            infrastructure=InfrastructureConfig(
                engine={"connector": _req(True)},
                sut={"connector": _req(True)},
            )
        )
        tck = _make_tck()
        tck._tests = [test]

        result = tck.infrastructure_requirements()

        assert result.engine["connector"].required is True
        assert result.sut["connector"].required is True

    def test_merge_unions_distinct_capability_keys(self) -> None:
        test_a = _make_test(infrastructure=InfrastructureConfig(engine={"connector": _req(True)}))
        test_b = _make_test(infrastructure=InfrastructureConfig(sut={"dtr": _req(True)}))
        tck = _make_tck()
        tck._tests = [test_a, test_b]

        result = tck.infrastructure_requirements()

        assert "connector" in result.engine
        assert "dtr" in result.sut

    def test_merge_required_true_wins_over_false(self) -> None:
        test_a = _make_test(infrastructure=InfrastructureConfig(engine={"dtr": _req(False)}))
        test_b = _make_test(infrastructure=InfrastructureConfig(engine={"dtr": _req(True)}))
        tck = _make_tck()
        tck._tests = [test_a, test_b]

        result = tck.infrastructure_requirements()

        assert result.engine["dtr"].required is True

    def test_merge_required_false_stays_false_when_both_false(self) -> None:
        test_a = _make_test(infrastructure=InfrastructureConfig(sut={"connector": _req(False)}))
        test_b = _make_test(infrastructure=InfrastructureConfig(sut={"connector": _req(False)}))
        tck = _make_tck()
        tck._tests = [test_a, test_b]

        result = tck.infrastructure_requirements()

        assert result.sut["connector"].required is False

    def test_merge_first_non_none_standard_wins(self) -> None:
        std = Standard(id="CX-0135", version="v3.1.0")
        test_a = _make_test(
            infrastructure=InfrastructureConfig(engine={"connector": _req(True, standard=std)})
        )
        test_b = _make_test(infrastructure=InfrastructureConfig(engine={"connector": _req(True)}))
        tck = _make_tck()
        tck._tests = [test_a, test_b]

        result = tck.infrastructure_requirements()

        assert result.engine["connector"].standard == std

    def test_merge_none_standard_inherits_later_non_none(self) -> None:
        std = Standard(id="CX-0018", version="v1.0")
        test_a = _make_test(infrastructure=InfrastructureConfig(sut={"connector": _req(True)}))
        test_b = _make_test(
            infrastructure=InfrastructureConfig(sut={"connector": _req(True, standard=std)})
        )
        tck = _make_tck()
        tck._tests = [test_a, test_b]

        result = tck.infrastructure_requirements()

        assert result.sut["connector"].standard == std


class TestInfrastructureRequirementsCcm:
    def test_ccm_tck_declares_engine_and_sut_connector(self) -> None:
        from tractusx_testlab.authoring.parser import YamlParser

        tck_def = YamlParser.parse_tck(CCM_RAW_DIR / "index.yaml")
        tck = Tck(tck_def)

        result = tck.infrastructure_requirements()

        assert result.engine["connector"].required is True
        assert result.sut["connector"].required is True

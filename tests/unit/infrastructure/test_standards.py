################################################################################
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
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Unit tests for the standard-to-service mapping — what a release means when wired."""

from __future__ import annotations

from tractusx_testlab.infrastructure.standards import (
    KNOWN_RELEASES,
    aas_api_path,
    connector_dialect,
    default_standard,
    is_known_release,
    release_or_default,
)
from tractusx_testlab.models.domain.infrastructure import ConnectorBinding, DtrBinding
from tractusx_testlab.player.execution.infrastructure_seeder import (
    _connector_definition,
    _dtr_definition,
)
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.syntax import defaults


class TestRelease:
    """The ecosystem release is what picks the dialect a service is built in."""

    def test_both_releases_are_known(self) -> None:
        assert set(KNOWN_RELEASES) == {"saturn", "jupiter"}

    def test_an_unstated_release_falls_back_to_the_engine_default(self) -> None:
        assert release_or_default("") == defaults.DATASPACE_VERSION

    def test_a_stated_release_is_kept(self) -> None:
        assert release_or_default("jupiter") == "jupiter"

    def test_an_unrecognised_release_is_reported_as_such(self) -> None:
        assert not is_known_release("pluto")


class TestCapabilityStandards:
    """Each capability implements a standard, unless none is assigned to it."""

    def test_a_connector_implements_the_connector_standard(self) -> None:
        assert default_standard("connector") == "CX-0018"

    def test_a_registry_implements_the_digital_twin_standard(self) -> None:
        assert default_standard("dtr") == "CX-0002"

    def test_the_submodel_server_claims_none(self) -> None:
        assert default_standard("submodel_server") == ""


class TestServiceWiring:
    """A release maps to concrete SDK wiring, in one table rather than in the seeder."""

    def test_the_connector_dialect_is_the_release(self) -> None:
        assert connector_dialect("jupiter") == "jupiter"

    def test_a_registry_answers_on_the_releases_aas_path(self) -> None:
        assert aas_api_path("saturn") == defaults.AAS_API_PATH

    def test_an_unknown_release_still_yields_a_usable_path(self) -> None:
        assert aas_api_path("pluto") == defaults.AAS_API_PATH


class TestSeededServices:
    """What the bindings carry is what the SDK service is built from."""

    def test_the_connector_is_built_for_the_bound_release(self) -> None:
        definition = _connector_definition(
            "c",
            ServiceType.CONNECTOR_CONSUMER,
            ConnectorBinding(management_url="https://c/management", version="jupiter"),
        )
        assert definition.params is not None
        assert definition.params["version"] == "jupiter"

    def test_a_connector_with_no_release_is_built_for_the_default(self) -> None:
        definition = _connector_definition(
            "c",
            ServiceType.CONNECTOR_CONSUMER,
            ConnectorBinding(management_url="https://c/management"),
        )
        assert definition.params is not None
        assert definition.params["version"] == defaults.DATASPACE_VERSION

    def test_the_registry_is_built_with_the_releases_api_path(self) -> None:
        definition = _dtr_definition("d", DtrBinding(base_url="https://d", version="saturn"))
        assert definition.params is not None
        assert definition.params["api_path"] == defaults.AAS_API_PATH

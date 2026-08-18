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

"""Unit tests for the InfrastructureManager — the deployments an engine can run against."""

from __future__ import annotations

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure.manager import InfrastructureManager
from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    InfrastructureConfig,
    Standard,
)
from tractusx_testlab.models.domain.infrastructure import (
    ConnectorBinding,
    DtrBinding,
    EngineBindings,
    EngineDtrBinding,
    Infrastructure,
    SutBindings,
)
from tractusx_testlab.models.primitives.exceptions import (
    InfrastructureError,
    MissingBindingError,
    StandardConflictError,
)


def _integration() -> Infrastructure:
    return Infrastructure(
        engine=EngineBindings(
            connector=ConnectorBinding(
                management_url="https://engine.example.com/management",
                api_key="engine-key",
                participant_id="BPNL000000000TLB",
            ),
            dtr=EngineDtrBinding(
                base_url="https://engine.example.com/semantics/registry",
                submodel_base_url="https://backend.example.com",
            ),
        ),
        sut=SutBindings(
            connector=ConnectorBinding(
                management_url="https://sut.example.com/management",
                participant_id="BPNL000000000001",
                dsp_url="https://sut.example.com/api/v1/dsp",
            ),
            dtr=DtrBinding(base_url="https://sut.example.com/semantics/registry"),
        ),
    )


def _staging() -> Infrastructure:
    return Infrastructure(
        sut=SutBindings(
            connector=ConnectorBinding(management_url="https://staging.example.com/management"),
        ),
    )


def _requires(**capabilities: bool) -> InfrastructureConfig:
    """Build a TCK requirement block for the SUT side."""
    return InfrastructureConfig(
        sut={
            key: CapabilityRequirement(required=value) for key, value in capabilities.items()
        },  # type: ignore[arg-type]
    )


class TestConstruction:
    """A deployment is handed to the manager as an object, not looked up by key."""

    def test_a_deployment_can_be_constructed_directly(self) -> None:
        manager = InfrastructureManager(_integration())
        assert manager.active.sut.connector.participant_id == "BPNL000000000001"

    def test_an_empty_manager_is_valid(self) -> None:
        assert InfrastructureManager().active == Infrastructure()

    def test_the_deployment_can_be_named(self) -> None:
        manager = InfrastructureManager(_integration(), name="integration")
        assert manager.active_name == "integration"

    def test_from_config_takes_the_engines_own_bindings(self) -> None:
        config = TestlabConfig(infrastructure=_integration())
        manager = InfrastructureManager.from_config(config)
        assert manager.active.engine.dtr.submodel_base_url == "https://backend.example.com"

    def test_from_env_reads_the_environment_over_a_base(self) -> None:
        manager = InfrastructureManager.from_env(
            {"TESTLAB_SUT_DTR_BASE_URL": "https://dtr.from.env"},
            base=_integration(),
        )
        assert manager.active.sut.dtr.base_url == "https://dtr.from.env"
        assert manager.active.sut.connector.participant_id == "BPNL000000000001"


class TestRegistry:
    """Several deployments live side by side and the active one is switched, not rebuilt."""

    def test_registered_deployments_are_listed(self) -> None:
        manager = InfrastructureManager(_integration(), name="integration")
        manager.register("staging", _staging())
        assert manager.names == ["integration", "staging"]

    def test_registering_does_not_activate_by_default(self) -> None:
        manager = InfrastructureManager(_integration(), name="integration")
        manager.register("staging", _staging())
        assert manager.active_name == "integration"

    def test_activate_switches_the_deployment(self) -> None:
        manager = InfrastructureManager(_integration(), name="integration")
        manager.register("staging", _staging())
        manager.activate("staging")
        assert manager.active.sut.connector.management_url == (
            "https://staging.example.com/management"
        )

    def test_registering_with_activate_switches_at_once(self) -> None:
        manager = InfrastructureManager(_integration(), name="integration")
        manager.register("staging", _staging(), activate=True)
        assert manager.active_name == "staging"

    def test_an_unregistered_name_is_named_in_the_error(self) -> None:
        manager = InfrastructureManager(_integration(), name="integration")
        with pytest.raises(InfrastructureError) as error:
            manager.activate("nope")
        assert "integration" in str(error.value)

    def test_overlay_writes_onto_the_active_deployment(self) -> None:
        manager = InfrastructureManager(_integration())
        manager.overlay(
            Infrastructure(sut=SutBindings(dtr=DtrBinding(base_url="https://dtr.overlaid")))
        )
        assert manager.active.sut.dtr.base_url == "https://dtr.overlaid"
        assert manager.active.engine.connector.api_key == "engine-key"


class TestResolve:
    """A run's own overrides apply to that run and to no other."""

    def test_overrides_are_applied(self) -> None:
        manager = InfrastructureManager(_integration())
        resolved = manager.resolve({"infrastructure.sut.dtr.base_url": "https://dtr.for.this.run"})
        assert resolved.sut.dtr.base_url == "https://dtr.for.this.run"

    def test_the_registered_deployment_is_not_modified(self) -> None:
        manager = InfrastructureManager(_integration())
        manager.resolve({"infrastructure.sut.dtr.base_url": "https://dtr.for.this.run"})
        assert manager.active.sut.dtr.base_url == "https://sut.example.com/semantics/registry"

    def test_no_overrides_returns_the_active_deployment(self) -> None:
        manager = InfrastructureManager(_integration())
        assert manager.resolve() == manager.active


class TestValidate:
    """A required capability with nothing behind it fails before the first step."""

    def test_a_bound_requirement_passes(self) -> None:
        InfrastructureManager(_integration()).validate(_requires(connector=True, dtr=True))

    def test_an_unbound_requirement_fails(self) -> None:
        manager = InfrastructureManager(_staging())
        with pytest.raises(MissingBindingError):
            manager.validate(_requires(dtr=True))

    def test_the_failure_names_the_capability_and_its_key(self) -> None:
        manager = InfrastructureManager(_staging())
        with pytest.raises(MissingBindingError) as error:
            manager.validate(_requires(dtr=True))
        message = str(error.value)
        assert "sut.dtr" in message
        assert "infrastructure.sut.dtr.base_url" in message
        assert "TESTLAB_SUT_DTR_BASE_URL" in message

    def test_every_missing_capability_is_reported_at_once(self) -> None:
        manager = InfrastructureManager()
        with pytest.raises(MissingBindingError) as error:
            manager.validate(_requires(connector=True, dtr=True))
        assert len(error.value.missing) == 2

    def test_an_optional_capability_is_not_required(self) -> None:
        InfrastructureManager().validate(_requires(connector=False, dtr=False))

    def test_a_capability_bound_only_by_a_qualifier_is_not_bound(self) -> None:
        """An api_key with no connector to send it to binds nothing."""
        manager = InfrastructureManager(
            Infrastructure(sut=SutBindings(connector=ConnectorBinding(api_key="orphan")))
        )
        with pytest.raises(MissingBindingError):
            manager.validate(_requires(connector=True))

    def test_validation_runs_against_a_resolved_deployment(self) -> None:
        """The run's overrides count — a capability bound by --var satisfies its requirement."""
        manager = InfrastructureManager(_staging())
        resolved = manager.resolve({"infrastructure.sut.dtr.base_url": "https://dtr.from.cli"})
        manager.validate(_requires(dtr=True), resolved)


def _requires_standard(capability: str, standard_id: str, version: str | None = None):
    """A SUT requirement that certifies against a named standard."""
    return InfrastructureConfig(
        sut={
            capability: CapabilityRequirement(
                required=True, standard=Standard(id=standard_id, version=version),
            ),
        },  # type: ignore[arg-type]
    )


class TestAlign:
    """What a TCK certifies against travels onto the deployment it runs against."""

    def test_the_release_is_inherited_from_the_tck(self) -> None:
        manager = InfrastructureManager(_integration())
        aligned = manager.align(_requires(connector=True), "jupiter")
        assert aligned.sut.connector.version == "jupiter"

    def test_the_release_reaches_every_bound_capability(self) -> None:
        manager = InfrastructureManager(_integration())
        aligned = manager.align(_requires(connector=True), "jupiter")
        assert aligned.sut.dtr.version == "jupiter"
        assert aligned.engine.connector.version == "jupiter"
        assert aligned.engine.dtr.version == "jupiter"

    def test_an_unbound_capability_is_left_alone(self) -> None:
        manager = InfrastructureManager(_staging())
        aligned = manager.align(_requires(connector=True), "jupiter")
        assert aligned.sut.dtr.version == ""

    def test_a_stated_release_is_kept(self) -> None:
        """An operator who knows their connector speaks another release has said so."""
        deployment = Infrastructure(
            sut=SutBindings(
                connector=ConnectorBinding(
                    management_url="https://sut/management", version="jupiter",
                ),
            ),
        )
        aligned = InfrastructureManager(deployment).align(
            InfrastructureConfig(), "jupiter", release_stated=False,
        )
        assert aligned.sut.connector.version == "jupiter"

    def test_a_contradicted_release_is_refused(self) -> None:
        deployment = Infrastructure(
            sut=SutBindings(
                connector=ConnectorBinding(
                    management_url="https://sut/management", version="jupiter",
                ),
            ),
        )
        with pytest.raises(StandardConflictError) as error:
            InfrastructureManager(deployment).align(_requires(connector=True), "saturn")
        message = str(error.value)
        assert "jupiter" in message and "saturn" in message

    def test_a_release_the_tck_never_stated_is_not_held_against_a_binding(self) -> None:
        deployment = Infrastructure(
            sut=SutBindings(
                connector=ConnectorBinding(
                    management_url="https://sut/management", version="jupiter",
                ),
            ),
        )
        aligned = InfrastructureManager(deployment).align(
            _requires(connector=True), "saturn", release_stated=False,
        )
        assert aligned.sut.connector.version == "jupiter"

    def test_the_standard_is_inherited_from_the_requirement(self) -> None:
        manager = InfrastructureManager(_integration())
        aligned = manager.align(_requires_standard("connector", "CX-0018", "2.1.3"), "saturn")
        assert aligned.sut.connector.standard == "CX-0018"
        assert aligned.sut.connector.standard_version == "2.1.3"

    def test_an_omitted_standard_version_inherits_the_release(self) -> None:
        manager = InfrastructureManager(_integration())
        aligned = manager.align(_requires_standard("dtr", "CX-0002"), "saturn")
        assert aligned.sut.dtr.standard_version == "saturn"

    def test_a_capability_the_tck_says_nothing_about_gets_its_usual_standard(self) -> None:
        manager = InfrastructureManager(_integration())
        aligned = manager.align(InfrastructureConfig(), "saturn")
        assert aligned.sut.connector.standard == "CX-0018"
        assert aligned.sut.dtr.standard == "CX-0002"

    def test_a_contradicted_standard_is_refused(self) -> None:
        deployment = Infrastructure(
            sut=SutBindings(
                connector=ConnectorBinding(
                    management_url="https://sut/management", standard="CX-0018",
                ),
            ),
        )
        with pytest.raises(StandardConflictError):
            InfrastructureManager(deployment).align(
                _requires_standard("connector", "CX-0126"), "saturn",
            )

    def test_the_default_standard_never_conflicts_with_a_stated_one(self) -> None:
        """The engine's fallback is a convenience, not a claim to hold anyone to."""
        deployment = Infrastructure(
            sut=SutBindings(
                connector=ConnectorBinding(
                    management_url="https://sut/management", standard="CX-0126",
                ),
            ),
        )
        aligned = InfrastructureManager(deployment).align(InfrastructureConfig(), "saturn")
        assert aligned.sut.connector.standard == "CX-0126"

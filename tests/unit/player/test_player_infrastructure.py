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

"""Tests for the infrastructure a player runs against — injected, resolved, checked."""

from __future__ import annotations

from pathlib import Path

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure.profiles import InfrastructureManager
from tractusx_testlab.models import Job
from tractusx_testlab.models.authoring.definitions import (
    TckDefinition,
    TckMetadataDefinition,
)
from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    DataspaceContext,
    InfrastructureConfig,
)
from tractusx_testlab.models.domain.infrastructure import (
    ConnectorBinding,
    Infrastructure,
    SutBindings,
)
from tractusx_testlab.models.primitives.exceptions import MissingBindingError
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.infrastructure_seeder import (
    seed_infrastructure_services,
)
from tractusx_testlab.player.execution.player import TestlabPlayer, _target_release
from tractusx_testlab.scripting.script import Tck
from tractusx_testlab.services.instances import ServiceManager


def _config(tmp_path: Path, infrastructure: Infrastructure | None = None) -> TestlabConfig:
    return TestlabConfig(
        logs_dir=tmp_path / "logs",
        infrastructure=infrastructure or Infrastructure(),
    )


def _sut_connector() -> Infrastructure:
    return Infrastructure(
        sut=SutBindings(
            connector=ConnectorBinding(
                management_url="https://sut.example.com/management",
                dsp_url="https://sut.example.com/api/v1/dsp",
            ),
        ),
    )


def _tck(release: str | None = None, **required: bool) -> Tck:
    """A TCK carrying the requirements — and optionally the release — under test.

    Built from the real models rather than a ``SimpleNamespace``.  A stub only
    has the attributes someone remembered to give it, so it agrees with whatever
    the code under test happens to read: when the player looked for
    a field the model does not declare, the stub was as silent about it as the
    real model, and the release fell back to the default with nobody the wiser.
    Using the declared models means a field that moves breaks this test instead
    of the run.
    """
    return Tck(
        TckDefinition(
            syntax="v1-alpha",
            id="infrastructure-probe",
            metadata=TckMetadataDefinition(name="Infrastructure probe"),
            dataspace=(
                DataspaceContext(ecosystem="Catena-X", version=release)
                if release is not None
                else None
            ),
            infrastructure=InfrastructureConfig(
                sut={
                    key: CapabilityRequirement(required=value)
                    for key, value in required.items()
                },  # type: ignore[arg-type]
            ),
        )
    )


def _context(player: TestlabPlayer, config: TestlabConfig) -> StepContext:
    return StepContext(
        services=ServiceManager(),
        job=Job(job_id="infrastructure-test"),
        config=config,
        infrastructure=player.infrastructure.active,
    )


class TestInjection:
    """The deployment is handed to the player as an object, not looked up by name."""

    def test_the_injected_manager_is_the_one_used(self, tmp_path: Path) -> None:
        manager = InfrastructureManager(_sut_connector(), name="integration")
        player = TestlabPlayer(config=_config(tmp_path), infrastructure=manager)
        assert player.infrastructure is manager

    def test_the_injected_deployment_reaches_the_run(self, tmp_path: Path) -> None:
        manager = InfrastructureManager(_sut_connector())
        player = TestlabPlayer(config=_config(tmp_path), infrastructure=manager)
        assert player.infrastructure.active.sut.connector.dsp_url == (
            "https://sut.example.com/api/v1/dsp"
        )

    def test_without_injection_the_config_supplies_the_deployment(self, tmp_path: Path) -> None:
        player = TestlabPlayer(config=_config(tmp_path, _sut_connector()))
        assert player.infrastructure.active.sut.connector.management_url == (
            "https://sut.example.com/management"
        )


class TestBinding:
    """A run resolves its bindings once, before the first step."""

    def test_bindings_are_published_as_variables(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager(_sut_connector()))
        context = _context(player, config)

        player._bind_infrastructure(context, _tck(connector=True))

        assert context.get_variable("infrastructure.sut.connector.dsp_url") == (
            "https://sut.example.com/api/v1/dsp"
        )

    def test_a_run_variable_overrides_the_deployment(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        manager = InfrastructureManager(_sut_connector())
        player = TestlabPlayer(config=config, infrastructure=manager)
        context = _context(player, config)
        context.set_variable("infrastructure.sut.dtr.base_url", "https://dtr.from.cli")

        player._bind_infrastructure(context, _tck(connector=True, dtr=True))

        assert context.infrastructure.sut.dtr.base_url == "https://dtr.from.cli"

    def test_an_overridden_run_does_not_change_the_deployment(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        manager = InfrastructureManager(_sut_connector())
        player = TestlabPlayer(config=config, infrastructure=manager)
        context = _context(player, config)
        context.set_variable("infrastructure.sut.dtr.base_url", "https://dtr.from.cli")

        player._bind_infrastructure(context, _tck(dtr=True))

        assert manager.active.sut.dtr.base_url == ""

    def test_the_context_carries_the_resolved_deployment(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager(_sut_connector()))
        context = _context(player, config)

        player._bind_infrastructure(context, _tck())

        assert context.infrastructure.sut.connector.is_bound()


class TestFailFast:
    """A capability a TCK requires and nobody bound stops the run before it starts."""

    def test_an_unbound_requirement_is_refused(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager())
        context = _context(player, config)

        with pytest.raises(MissingBindingError):
            player._bind_infrastructure(context, _tck(connector=True))

    def test_the_refusal_names_the_key_the_operator_owes(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager())
        context = _context(player, config)

        with pytest.raises(MissingBindingError) as error:
            player._bind_infrastructure(context, _tck(dtr=True))

        assert "infrastructure.sut.dtr.base_url" in str(error.value)

    def test_a_requirement_bound_at_run_time_is_accepted(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager())
        context = _context(player, config)
        context.set_variable("infrastructure.sut.dtr.base_url", "https://dtr.from.cli")

        player._bind_infrastructure(context, _tck(dtr=True))

        assert context.infrastructure.sut.dtr.base_url == "https://dtr.from.cli"


class TestRelease:
    """The ecosystem release the TCK targets is what the services are built for."""

    def test_the_tcks_release_reaches_the_bindings(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager(_sut_connector()))
        context = _context(player, config)

        player._bind_infrastructure(context, _tck(release="jupiter", connector=True))

        assert context.infrastructure.sut.connector.version == "jupiter"

    def test_the_release_is_published_as_a_variable(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager(_sut_connector()))
        context = _context(player, config)

        player._bind_infrastructure(context, _tck(release="jupiter", connector=True))

        assert context.get_variable("infrastructure.sut.connector.version") == "jupiter"

    def test_the_release_reaches_the_seeded_sdk_service(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        services = ServiceManager()
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager(_sut_connector()))
        context = StepContext(
            services=services,
            job=Job(job_id="release-test"),
            config=config,
            infrastructure=player.infrastructure.active,
        )

        player._bind_infrastructure(context, _tck(release="jupiter", connector=True))
        seed_infrastructure_services(services, context)

        definition = services._definitions["__sut_connector__"]
        assert definition.params is not None
        assert definition.params["version"] == "jupiter"

    def test_the_capabilitys_standard_is_recorded(self, tmp_path: Path) -> None:
        config = _config(tmp_path)
        player = TestlabPlayer(config=config, infrastructure=InfrastructureManager(_sut_connector()))
        context = _context(player, config)

        player._bind_infrastructure(context, _tck(release="saturn", connector=True))

        assert context.infrastructure.sut.connector.standard == "CX-0018"

    def test_the_dataspace_block_is_the_only_source_of_the_release(self) -> None:
        """``dataspace.version`` states the release; nothing else does.

        A flat ``dataspace_version`` field used to say the same thing in a second
        place, and the player read it off the definition — where it had never
        lived — so a TCK naming one release ran as another and reported the
        release as unstated, which is the flag that suppresses the conflict
        check. The field is gone; the block is the source.
        """
        tck = Tck(
            TckDefinition(
                syntax="v1-alpha",
                id="declared-release",
                metadata=TckMetadataDefinition(name="Declared"),
                dataspace=DataspaceContext(ecosystem="Catena-X", version="jupiter"),
            )
        )

        assert _target_release(tck) == ("jupiter", True)

    def test_an_undeclared_release_is_the_default_and_says_so(self, tmp_path: Path) -> None:
        """Nothing stated means the default release, flagged as *not* stated.

        The second half is what keeps the default from being held against an
        operator who bound a deployment of a different release.
        """
        tck = Tck(
            TckDefinition(
                syntax="v1-alpha",
                id="no-release",
                metadata=TckMetadataDefinition(name="No release"),
            )
        )

        assert _target_release(tck) == ("saturn", False)


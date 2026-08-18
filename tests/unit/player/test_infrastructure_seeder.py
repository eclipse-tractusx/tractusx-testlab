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
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-5.6 Sol).
## It was reviewed and tested by a human committer.

"""Unit tests for the infrastructure_seeder — ADR-0019 service auto-registration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tractusx_testlab.config.settings import TestlabConfig as _TestlabConfig
from tractusx_testlab.infrastructure.mapping import apply_overrides, collect_overrides
from tractusx_testlab.models import Job
from tractusx_testlab.models.domain.infrastructure import Infrastructure
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.infrastructure_seeder import (
    _ENGINE_CONNECTOR_NAME,
    _SUT_CONNECTOR_NAME,
    _SUT_DTR_NAME,
    seed_infrastructure_services,
)
from tractusx_testlab.services._sdk_services import is_type_compatible
from tractusx_testlab.services.instances import ServiceManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infrastructure(variables: dict) -> Infrastructure:
    """Resolve flat binding variables into the typed deployment they describe."""
    return apply_overrides(Infrastructure(), collect_overrides(variables))


def _make_context(variables: dict) -> MagicMock:
    """Return a lightweight StepContext mock backed by a real dict."""
    ctx = MagicMock()
    store: dict = dict(variables)
    ctx.variables = store
    ctx.set_variable.side_effect = lambda k, v: store.update({k: v})
    ctx.get_variable.side_effect = lambda k, d=None: store.get(k, d)
    ctx.get_str.side_effect = lambda k, d="": str(store.get(k, d) or d)
    ctx.infrastructure = _infrastructure(store)
    return ctx


def _base_engine_vars() -> dict:
    return {
        "infrastructure.engine.connector.management_url": "https://engine.example.com/management",
        "infrastructure.engine.connector.api_key": "key-engine",
    }


def _base_sut_vars() -> dict:
    return {
        "infrastructure.sut.connector.management_url": "https://sut.example.com/management",
        "infrastructure.sut.connector.api_key": "key-sut",
    }


# ---------------------------------------------------------------------------
# Engine connector registration
# ---------------------------------------------------------------------------

class TestEngineConnectorSeeding:
    """Engine connector is registered as CONNECTOR_CONSUMER."""

    def test_registers_engine_as_consumer(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(_base_engine_vars())

        seed_infrastructure_services(svc_mgr, ctx)

        assert _ENGINE_CONNECTOR_NAME in svc_mgr.service_names
        defn = svc_mgr._definitions[_ENGINE_CONNECTOR_NAME]
        assert defn.type == ServiceType.CONNECTOR_CONSUMER

    def test_engine_connector_context_var_is_set(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(_base_engine_vars())

        seed_infrastructure_services(svc_mgr, ctx)

        assert ctx.variables.get("infrastructure.engine.connector") == _ENGINE_CONNECTOR_NAME

    def test_strips_management_suffix_from_base_url(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(_base_engine_vars())

        seed_infrastructure_services(svc_mgr, ctx)

        defn = svc_mgr._definitions[_ENGINE_CONNECTOR_NAME]
        assert defn.base_url == "https://engine.example.com"
        assert defn.params is not None
        assert defn.params.get("dma_path") == "/management"

    def test_preserves_ingress_prefix_before_management_suffix(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context({
            "infrastructure.engine.connector.management_url": (
                "https://engine.example.com/connector/management"
            ),
        })

        seed_infrastructure_services(svc_mgr, ctx)

        defn = svc_mgr._definitions[_ENGINE_CONNECTOR_NAME]
        assert defn.base_url == "https://engine.example.com/connector"
        assert defn.params is not None
        assert defn.params.get("dma_path") == "/management"

    def test_no_registration_when_management_url_missing(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context({"infrastructure.engine.connector.api_key": "k"})

        seed_infrastructure_services(svc_mgr, ctx)

        assert _ENGINE_CONNECTOR_NAME not in svc_mgr.service_names


# ---------------------------------------------------------------------------
# Engine connector alias (provider role)
# ---------------------------------------------------------------------------

class TestEngineConnectorAlias:
    """When ``name`` field is set the engine connector is also registered as provider alias."""

    def _vars_with_name(self, alias: str = "testlab") -> dict:
        return {**_base_engine_vars(), "infrastructure.engine.connector.name": alias}

    def test_alias_registered_as_provider(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(self._vars_with_name("testlab"))

        seed_infrastructure_services(svc_mgr, ctx)

        assert "testlab" in svc_mgr.service_names
        defn = svc_mgr._definitions["testlab"]
        assert defn.type == ServiceType.CONNECTOR_PROVIDER

    def test_alias_same_base_url_as_engine(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(self._vars_with_name("testlab"))

        seed_infrastructure_services(svc_mgr, ctx)

        engine_defn = svc_mgr._definitions[_ENGINE_CONNECTOR_NAME]
        alias_defn = svc_mgr._definitions["testlab"]
        assert alias_defn.base_url == engine_defn.base_url

    def test_no_alias_when_name_not_set(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(_base_engine_vars())

        seed_infrastructure_services(svc_mgr, ctx)

        # Only internal name registered, no alias
        connector_names = svc_mgr.service_names
        assert _ENGINE_CONNECTOR_NAME in connector_names
        # No extra provider-type services from engine
        provider_defns = [
            n for n in connector_names
            if svc_mgr._definitions[n].type == ServiceType.CONNECTOR_PROVIDER
        ]
        assert provider_defns == []

    def test_existing_alias_not_overwritten(self) -> None:
        """An explicit ``services:`` block that already defines 'testlab' is not replaced."""
        from tractusx_testlab.models.authoring.definitions import ServiceDefinition
        original = ServiceDefinition(
            name="testlab",
            type=ServiceType.CONNECTOR_PROVIDER,
            base_url="https://explicit.example.com",
            auth={},
        )
        svc_mgr = ServiceManager()
        svc_mgr.register(original)
        ctx = _make_context(self._vars_with_name("testlab"))

        seed_infrastructure_services(svc_mgr, ctx)

        # Original must be preserved
        assert svc_mgr._definitions["testlab"].base_url == "https://explicit.example.com"


# ---------------------------------------------------------------------------
# SUT connector registration
# ---------------------------------------------------------------------------

class TestSutConnectorSeeding:
    """SUT connector is registered as CONNECTOR_PROVIDER."""

    def test_registers_sut_as_provider(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(_base_sut_vars())

        seed_infrastructure_services(svc_mgr, ctx)

        assert _SUT_CONNECTOR_NAME in svc_mgr.service_names
        defn = svc_mgr._definitions[_SUT_CONNECTOR_NAME]
        assert defn.type == ServiceType.CONNECTOR_PROVIDER

    def test_sut_context_var_is_set(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context(_base_sut_vars())

        seed_infrastructure_services(svc_mgr, ctx)

        assert ctx.variables.get("infrastructure.sut.connector") == _SUT_CONNECTOR_NAME


class TestConnectorRoleCompatibility:
    """Role-specific services resolve only to their declared connector role."""

    def test_consumer_does_not_satisfy_provider_role(self) -> None:
        assert not is_type_compatible(
            ServiceType.CONNECTOR_CONSUMER,
            ServiceType.CONNECTOR_PROVIDER,
        )

    def test_generic_connector_satisfies_provider_role(self) -> None:
        assert is_type_compatible(
            ServiceType.EDC_CONNECTOR_SATURN,
            ServiceType.CONNECTOR_PROVIDER,
        )

    def test_provider_lookup_skips_engine_consumer(self) -> None:
        svc_mgr = ServiceManager()
        bindings = {**_base_engine_vars(), **_base_sut_vars()}
        ctx = StepContext(
            services=svc_mgr,
            job=Job(job_id="provider-resolution-test"),
            config=_TestlabConfig(),
            infrastructure=_infrastructure(bindings),
        )
        for name, value in bindings.items():
            ctx.set_variable(name, value)
        seed_infrastructure_services(svc_mgr, ctx)

        with patch(
            "tractusx_testlab.services.instances.create_instance",
            side_effect=lambda definition, expected_type=None: definition.name,
        ):
            assert ctx.dataspace.provider() == _SUT_CONNECTOR_NAME


# ---------------------------------------------------------------------------
# DTR registration
# ---------------------------------------------------------------------------

class TestDtrSeeding:
    """SUT DTR service is registered from infrastructure.sut.dtr.* variables."""

    def test_registers_dtr(self) -> None:
        svc_mgr = ServiceManager()
        ctx = _make_context({"infrastructure.sut.dtr.base_url": "https://dtr.example.com/api/v3"})

        seed_infrastructure_services(svc_mgr, ctx)

        assert _SUT_DTR_NAME in svc_mgr.service_names
        defn = svc_mgr._definitions[_SUT_DTR_NAME]
        assert defn.type == ServiceType.DTR
        assert defn.base_url == "https://dtr.example.com/api/v3"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestSeederIdempotency:
    """Calling seed_infrastructure_services twice is safe and produces no duplicates."""

    def test_double_seed_is_idempotent(self) -> None:
        svc_mgr = ServiceManager()
        vars_ = {**_base_engine_vars(), **_base_sut_vars()}
        ctx = _make_context(vars_)

        seed_infrastructure_services(svc_mgr, ctx)
        first_names = set(svc_mgr.service_names)

        seed_infrastructure_services(svc_mgr, ctx)
        second_names = set(svc_mgr.service_names)

        assert first_names == second_names

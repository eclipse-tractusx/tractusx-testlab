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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Register SDK services for the infrastructure a run was bound to (ADR-0019).

Reads the typed :class:`Infrastructure` the player resolved onto the context
and registers the corresponding SDK service instances in the ``ServiceManager``
before test execution begins. This is the seam where the declarative topology
model becomes live services, so a TCK whose only runtime input is a config
block drives real connector calls without an explicit ``services:`` block.

The bindings arrive already resolved and validated; nothing here recovers a
field from a string key, and a capability that was never bound is simply not
registered rather than half-registered from whatever happened to be present.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.infrastructure.standards import aas_api_path, connector_dialect
from tractusx_testlab.models.authoring.definitions import ServiceDefinition
from tractusx_testlab.models.domain.infrastructure import (
    ConnectorBinding,
    DtrBinding,
)
from tractusx_testlab.models.primitives.enums import ServiceType

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.services.instances import ServiceManager

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Stable internal service names — unique to avoid collisions with user-defined
# services, and the values the ``infrastructure.<side>.<capability>`` variables
# resolve to so a step param can name a seeded service.
# ------------------------------------------------------------------

_ENGINE_CONNECTOR_NAME = "__engine_connector__"
_ENGINE_DTR_NAME = "__engine_dtr__"
_SUT_CONNECTOR_NAME = "__sut_connector__"
_SUT_DTR_NAME = "__sut_dtr__"

# Management path suffixes recognised when stripping to derive base_url.
_KNOWN_MANAGEMENT_SUFFIXES: tuple[str, ...] = ("/management", "/api/v1/management")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _strip_management_suffix(url: str) -> tuple[str, str]:
    """Return ``(base_url, dma_path)`` by stripping a known management suffix.

    If no known suffix is found, returns the original URL as ``base_url`` and
    an empty string as ``dma_path`` so the SDK uses the URL as-is.
    """
    clean = url.rstrip("/")
    for suffix in _KNOWN_MANAGEMENT_SUFFIXES:
        if clean.endswith(suffix):
            return clean[: -len(suffix)], suffix
    return clean, ""


def _connector_definition(
    name: str,
    service_type: ServiceType,
    binding: ConnectorBinding,
) -> ServiceDefinition:
    """Build a ``ServiceDefinition`` for a bound connector.

    The ecosystem release the binding carries picks the SDK dialect — the
    Saturn or Jupiter connector service — and it got there from the TCK's
    ``dataspace.version`` unless the operator stated one of their own.
    """
    base_url, dma_path = _strip_management_suffix(binding.management_url)

    params: dict = {
        "version": connector_dialect(binding.version),
        "dma_path": dma_path,
    }
    if binding.participant_id:
        params["participant_id"] = binding.participant_id
    if binding.dsp_url:
        params["dsp_url"] = binding.dsp_url

    auth: dict = {}
    if binding.api_key:
        auth = {"api_key": binding.api_key, "api_key_header": binding.api_key_header}

    return ServiceDefinition(
        name=name,
        type=service_type,
        base_url=base_url,
        auth=auth,
        params=params,
    )


def _dtr_definition(name: str, binding: DtrBinding) -> ServiceDefinition:
    """Build a ``ServiceDefinition`` for a bound Digital Twin Registry.

    The AAS API path comes from the ecosystem release rather than from the
    address, because it is the registry's API generation and not part of the
    host an operator was given.
    """
    return ServiceDefinition(
        name=name,
        type=ServiceType.DTR,
        base_url=binding.base_url,
        auth={},
        params={"api_path": aas_api_path(binding.version)},
    )


def _register(
    svc_mgr: ServiceManager,
    context: StepContext,
    definition: ServiceDefinition,
    capability_key: str,
) -> None:
    """Register *definition* and publish the name under its capability key."""
    svc_mgr.register(definition)
    context.set_variable(capability_key, definition.name)
    logger.info(
        "Seeded %s service '%s' from infrastructure bindings (base_url=%s)",
        capability_key, definition.name, definition.base_url,
    )


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def seed_infrastructure_services(
    svc_mgr: ServiceManager, context: StepContext,
) -> None:
    """Register the SDK services the run's infrastructure bindings describe.

    Called once by the player after the bindings are resolved and validated,
    before any test execution begins. Already-registered services are never
    overwritten, so an explicit ``services:`` block in the YAML always takes
    precedence.

    Registration order decides which service a role lookup finds first, so the
    SUT connector and registry are registered ahead of the engine's own: a
    provider or registry step is asking about the system under test.
    """
    already = set(svc_mgr.service_names)
    infrastructure = context.infrastructure

    # engine.connector → CONNECTOR_CONSUMER (the engine talks to the SUT as consumer)
    engine_connector = infrastructure.engine.connector
    if engine_connector.is_bound() and _ENGINE_CONNECTOR_NAME not in already:
        _register(
            svc_mgr,
            context,
            _connector_definition(
                _ENGINE_CONNECTOR_NAME, ServiceType.CONNECTOR_CONSUMER, engine_connector,
            ),
            "infrastructure.engine.connector",
        )

        # The same connector also acts as a provider when a script names it,
        # which is what ``name`` binds: ``service: testlab`` in a provision
        # step resolves to the engine's own connector under that alias.
        alias = engine_connector.name
        if alias and alias not in already:
            svc_mgr.register(
                _connector_definition(alias, ServiceType.CONNECTOR_PROVIDER, engine_connector)
            )
            logger.info(
                "Seeded engine connector provider alias '%s' from infrastructure bindings",
                alias,
            )

    # sut.connector → CONNECTOR_PROVIDER (the component under test)
    sut_connector = infrastructure.sut.connector
    if sut_connector.is_bound() and _SUT_CONNECTOR_NAME not in already:
        _register(
            svc_mgr,
            context,
            _connector_definition(
                _SUT_CONNECTOR_NAME, ServiceType.CONNECTOR_PROVIDER, sut_connector,
            ),
            "infrastructure.sut.connector",
        )

    # sut.dtr → DTR (the registry under test)
    sut_dtr = infrastructure.sut.dtr
    if sut_dtr.is_bound() and _SUT_DTR_NAME not in already:
        _register(
            svc_mgr, context, _dtr_definition(_SUT_DTR_NAME, sut_dtr), "infrastructure.sut.dtr",
        )

    # engine.dtr → DTR (the engine's own registry, registered last so a bare
    # registry lookup still finds the system under test)
    engine_dtr = infrastructure.engine.dtr
    if engine_dtr.is_bound() and _ENGINE_DTR_NAME not in already:
        _register(
            svc_mgr,
            context,
            _dtr_definition(_ENGINE_DTR_NAME, engine_dtr),
            "infrastructure.engine.dtr",
        )

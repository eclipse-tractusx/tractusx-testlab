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

"""Seed connector services from ``infrastructure.*`` context variables (ADR-0019).

Reads flat variables whose keys begin with ``infrastructure.engine.connector.*``,
``infrastructure.sut.connector.*``, or ``infrastructure.sut.dtr.*`` and
auto-registers the corresponding SDK service instances in the ``ServiceManager``
before test execution begins.

This bridges the gap between the declarative topology model (ADR-0019) and the
SDK service layer, enabling TCKs whose only runtime input is a config YAML
to drive real connector calls without an explicit ``services:`` block.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tractusx_testlab.models.authoring.definitions import ServiceDefinition
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.syntax import defaults

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.services.manager import ServiceManager

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Infrastructure variable prefixes (ADR-0019 §1)
# ------------------------------------------------------------------

_ENGINE_CONNECTOR_PREFIX = "infrastructure.engine.connector."
_SUT_CONNECTOR_PREFIX = "infrastructure.sut.connector."
_SUT_DTR_PREFIX = "infrastructure.sut.dtr."

# Stable internal service names — unique to avoid collisions with user-defined services.
_ENGINE_CONNECTOR_NAME = "__engine_connector__"
_SUT_CONNECTOR_NAME = "__sut_connector__"
_SUT_DTR_NAME = "__sut_dtr__"

# Management path suffixes recognised when stripping to derive base_url.
_KNOWN_MANAGEMENT_SUFFIXES: tuple[str, ...] = ("/management", "/api/v1/management")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _collect_prefix(variables: dict, prefix: str) -> dict[str, str]:
    """Return sub-key → value pairs for all variables starting with *prefix*."""
    result: dict[str, str] = {}
    for key, value in variables.items():
        if key.startswith(prefix):
            sub_key = key[len(prefix):]
            result[sub_key] = str(value) if value is not None else ""
    return result


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


def _build_connector_definition(
    name: str,
    service_type: ServiceType,
    fields: dict[str, str],
) -> ServiceDefinition | None:
    """Build a ``ServiceDefinition`` from extracted connector fields.

    Returns ``None`` if no management URL can be determined.
    """
    management_url = fields.get("management_url") or fields.get("base_url", "")
    if not management_url:
        logger.debug("No management_url for service '%s' — skipping", name)
        return None

    base_url, dma_path = _strip_management_suffix(management_url)
    api_key = fields.get("api_key", "")
    api_key_header = fields.get("api_key_header", "x-api-key")
    version = fields.get("version") or defaults.DATASPACE_VERSION

    params: dict = {"version": version, "dma_path": dma_path}

    participant_id = fields.get("participant_id")
    if participant_id:
        params["participant_id"] = participant_id

    dsp_url = fields.get("dsp_url")
    if dsp_url:
        params["dsp_url"] = dsp_url

    auth: dict = {}
    if api_key:
        auth = {"api_key": api_key, "api_key_header": api_key_header}

    return ServiceDefinition(
        name=name,
        type=service_type,
        base_url=base_url,
        auth=auth,
        params=params,
    )


def _build_dtr_definition(name: str, fields: dict[str, str]) -> ServiceDefinition | None:
    """Build a DTR ``ServiceDefinition`` from extracted fields."""
    base_url = fields.get("base_url") or fields.get("api_url", "")
    if not base_url:
        logger.debug("No base_url for DTR service '%s' — skipping", name)
        return None

    return ServiceDefinition(
        name=name,
        type=ServiceType.DTR,
        base_url=base_url,
        auth={},
        params=None,
    )


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def seed_infrastructure_services(
    svc_mgr: "ServiceManager", context: "StepContext",
) -> None:
    """Register infrastructure connector services derived from context variables.

    Reads the ``infrastructure.*`` flat variables already loaded into *context*
    and registers the corresponding services in *svc_mgr*.

    Called once by the player after ``_seed_context_variables``, before any
    test execution begins.  Already-registered services are never overwritten so
    that an explicit ``services:`` block in the YAML always takes precedence.
    """
    already = set(svc_mgr.service_names)
    all_vars = context.variables

    # engine.connector → CONNECTOR_CONSUMER (testlab engine talks to SUT as consumer)
    if _ENGINE_CONNECTOR_NAME not in already:
        engine_fields = _collect_prefix(all_vars, _ENGINE_CONNECTOR_PREFIX)
        if engine_fields:
            defn = _build_connector_definition(
                _ENGINE_CONNECTOR_NAME,
                ServiceType.CONNECTOR_CONSUMER,
                engine_fields,
            )
            if defn:
                svc_mgr.register(defn)
                # Expose the service name so ${{ infrastructure.engine.connector }}
                # resolves to a named service lookup in step params.
                context.set_variable("infrastructure.engine.connector", _ENGINE_CONNECTOR_NAME)
                logger.info(
                    "Seeded engine connector service '%s' from infrastructure variables "
                    "(base_url=%s)", _ENGINE_CONNECTOR_NAME, defn.base_url,
                )

            # Also register engine connector as CONNECTOR_PROVIDER under its alias
            # so that ``service: testlab`` in provision steps resolves correctly.
            engine_alias = engine_fields.get("name")
            if engine_alias and engine_alias not in already:
                alias_defn = _build_connector_definition(
                    engine_alias,
                    ServiceType.CONNECTOR_PROVIDER,
                    engine_fields,
                )
                if alias_defn:
                    svc_mgr.register(alias_defn)
                    logger.info(
                        "Seeded engine connector provider alias '%s' from infrastructure variables "
                        "(base_url=%s)", engine_alias, alias_defn.base_url,
                    )

    # sut.connector → CONNECTOR_PROVIDER (the component under test)
    if _SUT_CONNECTOR_NAME not in already:
        sut_fields = _collect_prefix(all_vars, _SUT_CONNECTOR_PREFIX)
        if sut_fields:
            defn = _build_connector_definition(
                _SUT_CONNECTOR_NAME,
                ServiceType.CONNECTOR_PROVIDER,
                sut_fields,
            )
            if defn:
                svc_mgr.register(defn)
                context.set_variable("infrastructure.sut.connector", _SUT_CONNECTOR_NAME)
                logger.info(
                    "Seeded SUT connector service '%s' from infrastructure variables "
                    "(base_url=%s)", _SUT_CONNECTOR_NAME, defn.base_url,
                )

    # sut.dtr → DTR (optional)
    if _SUT_DTR_NAME not in already:
        dtr_fields = _collect_prefix(all_vars, _SUT_DTR_PREFIX)
        if dtr_fields:
            defn = _build_dtr_definition(_SUT_DTR_NAME, dtr_fields)
            if defn:
                svc_mgr.register(defn)
                context.set_variable("infrastructure.sut.dtr", _SUT_DTR_NAME)
                logger.info(
                    "Seeded SUT DTR service '%s' from infrastructure variables "
                    "(base_url=%s)", _SUT_DTR_NAME, defn.base_url,
                )

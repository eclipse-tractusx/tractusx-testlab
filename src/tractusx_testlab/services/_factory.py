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
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-5.6 Sol).
## It was reviewed and tested by a human committer.

"""SDK service instance creation — wires ServiceDefinitions to live SDK objects."""

from __future__ import annotations

import logging
from typing import Optional

from tractusx_testlab.models.authoring.definitions import ServiceDefinition
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.syntax import defaults

logger = logging.getLogger(__name__)

# All connector service types. Role-specific consumer/provider definitions are
# deliberately not interchangeable; only the generic EDC types satisfy either role.
_CONNECTOR_TYPES: frozenset[str] = frozenset({
    "CONNECTOR_CONSUMER", "CONNECTOR_PROVIDER",
    "EDC_CONNECTOR", "EDC_CONNECTOR_SATURN", "EDC_CONNECTOR_JUPITER",
})

# Generic connector types that don't specify a consumer/provider role.
_GENERIC_CONNECTOR_TYPES: frozenset[str] = frozenset({
    "EDC_CONNECTOR", "EDC_CONNECTOR_SATURN", "EDC_CONNECTOR_JUPITER",
})

# Types that map to DTR / AAS service.
_DTR_COMPATIBLE_TYPES: frozenset[str] = frozenset({"DTR", "DIGITAL_TWIN_REGISTRY"})

# Inferred dataspace version from extended type names.
_VERSION_FROM_TYPE: dict[str, str] = {
    "EDC_CONNECTOR_SATURN": "saturn",
    "EDC_CONNECTOR_JUPITER": "jupiter",
}


def is_type_compatible(actual: ServiceType, expected: ServiceType) -> bool:
    """Check if *actual* service type is compatible with *expected* role."""
    actual_val = actual.value
    expected_val = expected.value
    if actual_val == expected_val:
        return True
    if (
        actual_val in _CONNECTOR_TYPES
        and expected_val in _CONNECTOR_TYPES
        and (actual_val in _GENERIC_CONNECTOR_TYPES or expected_val in _GENERIC_CONNECTOR_TYPES)
    ):
        return True
    if actual_val in _DTR_COMPATIBLE_TYPES and expected_val in _DTR_COMPATIBLE_TYPES:
        return True
    return False


def cache_key(
    name: str, definition: ServiceDefinition, expected_type: Optional[ServiceType],
) -> str:
    """Return cache key — compound for generic connector types."""
    if expected_type and definition.type.value in _GENERIC_CONNECTOR_TYPES:
        return f"{name}:{expected_type.value}"
    return name


def create_instance(
    service_definition: ServiceDefinition, expected_type: Optional[ServiceType] = None,
) -> object:
    """Create a live SDK service from a ServiceDefinition."""
    stype_val = service_definition.type.value

    if stype_val in _CONNECTOR_TYPES:
        return _create_connector_service(service_definition, expected_type)
    if stype_val in _DTR_COMPATIBLE_TYPES:
        return _create_aas_service(service_definition)

    from tractusx_testlab.models import ServiceNotFoundError
    raise ServiceNotFoundError(service_definition.name)


def _create_connector_service(
    service_definition: ServiceDefinition, expected_type: Optional[ServiceType] = None,
) -> object:
    from tractusx_sdk.dataspace.services.connector.service_factory import ServiceFactory

    auth = service_definition.auth
    params = service_definition.params or {}
    stype_val = service_definition.type.value
    version = params.get("version") or _VERSION_FROM_TYPE.get(stype_val, defaults.DATASPACE_VERSION)
    dma_path = params.get("dma_path", defaults.DMA_PATH)

    # Always include Content-Type because the SDK sends POST bodies via
    # data= (not json=), so requests does not set it automatically.
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if auth.get("api_key"):
        key_header = auth.get("api_key_header", "x-api-key").lower()
        headers[key_header] = auth["api_key"]

    is_provider = (
        stype_val == "CONNECTOR_PROVIDER"
        or (expected_type is not None and expected_type.value == "CONNECTOR_PROVIDER")
    )

    if is_provider:
        return ServiceFactory.get_connector_provider_service(
            dataspace_version=version,
            base_url=service_definition.base_url,
            dma_path=dma_path,
            headers=headers or None,
        )
    return ServiceFactory.get_connector_consumer_service(
        dataspace_version=version,
        base_url=service_definition.base_url,
        dma_path=dma_path,
        headers=headers or None,
    )


def _create_aas_service(service_definition: ServiceDefinition) -> object:
    from tractusx_sdk.industry.services.aas_service import AasService

    params = service_definition.params or {}
    return AasService(
        base_url=service_definition.base_url,
        base_lookup_url=params.get("base_lookup_url", service_definition.base_url),
        api_path=params.get("api_path", defaults.AAS_API_PATH),
    )

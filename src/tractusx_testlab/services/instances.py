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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""ServiceManager — lifecycle facade for SDK service instances.

Delegates creation/wiring to ``_factory`` and owns registration, caching,
state tracking, and teardown.
"""

from __future__ import annotations

import logging

from tractusx_testlab.models import (
    ServiceNotFoundError,
    ServiceState,
)
from tractusx_testlab.models.authoring.definitions import ServiceDefinition
from tractusx_testlab.models.primitives.enums import ServiceType
from tractusx_testlab.services._sdk_services import (
    cache_key,
    create_instance,
    is_type_compatible,
)

logger = logging.getLogger(__name__)


class ServiceManager:
    """Lifecycle manager for SDK service instances referenced by test scripts.

    Services are declared in the YAML script ``services:`` block, then initialised
    lazily on first access and cached for the lifetime of the execution.
    """

    __slots__ = ("_definitions", "_instances", "_states")

    def __init__(self) -> None:
        self._definitions: dict[str, ServiceDefinition] = {}
        self._instances: dict[str, object] = {}
        self._states: dict[str, ServiceState] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, definition: ServiceDefinition) -> None:
        """Register a service definition from the script."""
        self._definitions[definition.name] = definition
        self._states[definition.name] = ServiceState.DECLARED

    def register_all(self, definitions: list[ServiceDefinition]) -> None:
        """Register multiple service definitions at once."""
        for definition in definitions:
            self.register(definition)

    # ------------------------------------------------------------------
    # Retrieval (lazy init)
    # ------------------------------------------------------------------

    def get(self, name: str, expected_type: ServiceType | None = None) -> object:
        """Return a live service instance, initialising it if necessary."""
        if name not in self._definitions:
            raise ServiceNotFoundError(name)

        service_definition = self._definitions[name]
        if expected_type and not is_type_compatible(service_definition.type, expected_type):
            raise ValueError(
                f"Service '{name}' is {service_definition.type.value}, expected {expected_type.value}"
            )

        key = cache_key(name, service_definition, expected_type)
        if key in self._instances:
            return self._instances[key]

        logger.info("Initialising service '%s' (%s)", name, service_definition.type.value)
        self._states[name] = ServiceState.INITIALIZING

        instance = create_instance(service_definition, expected_type)
        self._instances[key] = instance
        self._states[name] = ServiceState.READY
        return instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def state(self, name: str) -> ServiceState:
        """Return the current lifecycle state of a service."""
        return self._states.get(name, ServiceState.DECLARED)

    def teardown(self) -> None:
        """Release all service instances."""
        self._instances.clear()
        for name in self._states:
            self._states[name] = ServiceState.STOPPED
        logger.info("All services torn down")

    def definition_of_type(self, stype: ServiceType) -> ServiceDefinition | None:
        """The first declaration matching *stype*, or ``None``.

        A public way to ask, because the caller that needed it was reaching into
        ``self._definitions`` from another module.
        """
        for declared in self._definitions.values():
            if declared.type == stype:
                return declared
        return None

    @property
    def service_names(self) -> list[str]:
        """Return the names of all registered services."""
        return list(self._definitions.keys())

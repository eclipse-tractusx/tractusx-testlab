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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""StepContext — the execution context passed to every step.

Provides access to services, variables, job memory, and configuration.
"""

from __future__ import annotations

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job, ServiceDefinition, ServiceNotFoundError, ServiceType
from tractusx_testlab.services.manager import ServiceManager
from tractusx_testlab.syntax import defaults


class StepContext:
    """Mutable execution context shared across steps within a single script run."""

    __slots__ = ("_services", "_variables", "_job", "_config")

    def __init__(
        self,
        services: ServiceManager,
        job: Job,
        config: TestlabConfig,
    ) -> None:
        self._services = services
        self._job = job
        self._config = config
        self._variables: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def config(self) -> TestlabConfig:
        return self._config

    @property
    def services(self) -> ServiceManager:
        return self._services

    # ------------------------------------------------------------------
    # Job / Memory
    # ------------------------------------------------------------------

    @property
    def job(self) -> Job:
        return self._job

    # ------------------------------------------------------------------
    # Variables (script-scoped, resolved from step params with ${...})
    # ------------------------------------------------------------------

    def set_variable(self, name: str, value: object) -> None:
        self._variables[name] = value

    def get_variable(self, name: str, default: object = None) -> object:
        return self._variables.get(name, default)

    def has_variable(self, name: str) -> bool:
        return name in self._variables

    @property
    def variables(self) -> dict[str, object]:
        return dict(self._variables)

    # ------------------------------------------------------------------
    # Service accessors (delegates to ServiceManager)
    # ------------------------------------------------------------------

    def get_provider_service(self) -> object:
        """Return the CONNECTOR_PROVIDER service the run was seeded with."""
        return self._first_service_of_type(ServiceType.CONNECTOR_PROVIDER)

    def get_consumer_service(self) -> object:
        """Return the CONNECTOR_CONSUMER service the run was seeded with."""
        return self._first_service_of_type(ServiceType.CONNECTOR_CONSUMER)

    def get_aas_service(self) -> object:
        """Return the DTR / AAS service the run was seeded with."""
        return self._first_service_of_type(ServiceType.DTR)

    def get_notification_service(self) -> object:
        """Return the service notifications are sent through.

        Notifications ride on the connector consumer, so there is no service of
        their own to look up.
        """
        return self._first_service_of_type(ServiceType.CONNECTOR_CONSUMER)

    def _first_service_of_type(self, stype: ServiceType) -> object:
        """Return the first registered service matching *stype*."""
        for svc_name in self._services.service_names:
            try:
                return self._services.get(svc_name, stype)
            except (ServiceNotFoundError, ValueError):
                continue
        raise ServiceNotFoundError(f"No service of type {stype.value} is registered")

    def _first_definition_of_type(self, stype: ServiceType) -> "ServiceDefinition | None":
        """Return the first ``ServiceDefinition`` matching *stype*, or ``None``."""
        for service_definition in self._services._definitions.values():
            if service_definition.type == stype:
                return service_definition
        return None

    def _get_base_url(self, stype: ServiceType) -> str:
        """Return ``base_url + dma_path`` for the first service of *stype*.

        Avoids doubling the management path if the base_url already ends with it.
        """
        service_definition = self._first_definition_of_type(stype)
        if service_definition is None:
            return ""
        dma = (service_definition.params or {}).get("dma_path", defaults.DMA_PATH)
        base = service_definition.base_url.rstrip("/")
        if base.endswith(dma.rstrip("/")):
            return base
        return f"{base}{dma}"

    def get_provider_base_url(self) -> str:
        """Return ``base_url + dma_path`` for the first provider service."""
        return self._get_base_url(ServiceType.CONNECTOR_PROVIDER)

    def get_consumer_base_url(self) -> str:
        """Return ``base_url + dma_path`` for the first consumer service."""
        return self._get_base_url(ServiceType.CONNECTOR_CONSUMER)

    # ------------------------------------------------------------------
    # Management-API endpoint URLs (for step request reporting)
    # ------------------------------------------------------------------

    @staticmethod
    def _controller_url(service: object, fallback_base: str, controller: str, *segments: object) -> str:
        """Join an SDK controller's endpoint path onto its connector base URL.

        The versioned management path (``/v3/catalog`` and friends) differs per
        dataspace version, so it is read off the controller the SDK built for
        the configured version instead of being spelled out here. When the
        service does not expose that controller — a stub, or a version that
        dropped it — only the base URL and the extra segments are returned.
        """
        controller_obj = getattr(service, controller, None)
        base = getattr(getattr(controller_obj, "adapter", None), "base_url", None)
        if not isinstance(base, str) or not base:
            base = fallback_base
        if not base:
            # No connector configured — a bare path would read as a real URL.
            return ""
        endpoint = getattr(controller_obj, "endpoint_url", None)

        parts = [base.rstrip("/")]
        if isinstance(endpoint, str):
            parts.append(endpoint.strip("/"))
        parts.extend(str(segment).strip("/") for segment in segments if segment is not None)
        return "/".join(part for part in parts if part)

    def get_consumer_endpoint_url(self, controller: str, *segments: object) -> str:
        """Return the consumer management-API URL of an SDK *controller*.

        ``controller`` is the SDK consumer-service attribute holding it, e.g.
        ``"catalogs"``, ``"edrs"`` or ``"transfer_processes"``; *segments* are
        appended as further path elements.
        """
        try:
            consumer = self.get_consumer_service()
        except ServiceNotFoundError:
            consumer = None
        return self._controller_url(consumer, self.get_consumer_base_url(), controller, *segments)

    def get_provider_endpoint_url(self, controller: str, *segments: object) -> str:
        """Return the provider management-API URL of an SDK *controller*.

        ``controller`` is the SDK provider-service attribute holding it, e.g.
        ``"assets"``, ``"policies"`` or ``"contract_definitions"``.
        """
        try:
            provider = self.get_provider_service()
        except ServiceNotFoundError:
            provider = None
        return self._controller_url(provider, self.get_provider_base_url(), controller, *segments)

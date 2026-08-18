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

"""Reaching the dataspace services a run was seeded with.

This used to live on :class:`StepContext`, which meant the context every step
receives — variables, job, config, infrastructure — also carried eight
connector-shaped accessors and an SDK controller URL builder. A ``util/log``
step and a DSP negotiation step were handed the same object, and it knew about
catalogs either way.

Split out, ``StepContext`` is about a run and this is about the dataspace, which
is also what makes each readable on its own.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.contracts import (
    ConnectorConsumer,
    ConnectorProvider,
    NotificationService,
    RegistryService,
)
from tractusx_testlab.models import ServiceNotFoundError, ServiceType
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.syntax import defaults


class DataspaceAccess:
    """The seeded connector, registry and notification services, and their URLs."""

    __slots__ = ("_services",)

    def __init__(self, services: ServiceManager) -> None:
        self._services = services

    # ------------------------------------------------------------------
    # The services themselves
    # ------------------------------------------------------------------

    def provider(self) -> ConnectorProvider:
        """The CONNECTOR_PROVIDER service the run was seeded with."""
        return self._first_of(ServiceType.CONNECTOR_PROVIDER)

    def consumer(self) -> ConnectorConsumer:
        """The CONNECTOR_CONSUMER service the run was seeded with."""
        return self._first_of(ServiceType.CONNECTOR_CONSUMER)

    def registry(self) -> RegistryService:
        """The DTR / AAS service the run was seeded with."""
        return self._first_of(ServiceType.DTR)

    def notifications(self) -> NotificationService:
        """The service notifications are sent through.

        Notifications ride on the connector consumer, so there is no service of
        their own to look up.
        """
        return self._first_of(ServiceType.CONNECTOR_CONSUMER)

    def _first_of(self, stype: ServiceType) -> Any:
        for name in self._services.service_names:
            try:
                return self._services.get(name, stype)
            except (ServiceNotFoundError, ValueError):
                continue
        raise ServiceNotFoundError(f"No service of type {stype.value} is registered")

    # ------------------------------------------------------------------
    # Base URLs
    # ------------------------------------------------------------------

    def provider_base_url(self) -> str:
        """``base_url + dma_path`` for the first provider service."""
        return self._base_url(ServiceType.CONNECTOR_PROVIDER)

    def consumer_base_url(self) -> str:
        """``base_url + dma_path`` for the first consumer service."""
        return self._base_url(ServiceType.CONNECTOR_CONSUMER)

    def _base_url(self, stype: ServiceType) -> str:
        """Avoids doubling the management path when base_url already ends with it."""
        declared = self._services.definition_of_type(stype)
        if declared is None:
            return ""
        dma = (declared.params or {}).get("dma_path", defaults.DMA_PATH)
        base = declared.base_url.rstrip("/")
        return base if base.endswith(dma.rstrip("/")) else f"{base}{dma}"

    # ------------------------------------------------------------------
    # Management-API endpoint URLs, for reporting what a step called
    # ------------------------------------------------------------------

    def consumer_endpoint_url(self, controller: str, *segments: object) -> str:
        """The consumer management-API URL of an SDK *controller*.

        ``controller`` is the SDK attribute holding it — ``"catalogs"``,
        ``"edrs"``, ``"transfer_processes"`` — and *segments* are appended as
        further path elements.
        """
        return self._controller_url(
            self._or_none(self.consumer), self.consumer_base_url(), controller, *segments
        )

    def provider_endpoint_url(self, controller: str, *segments: object) -> str:
        """The provider management-API URL of an SDK *controller*.

        ``controller`` is ``"assets"``, ``"policies"`` or
        ``"contract_definitions"``.
        """
        return self._controller_url(
            self._or_none(self.provider), self.provider_base_url(), controller, *segments
        )

    @staticmethod
    def _or_none(lookup: Any) -> Any:
        try:
            return lookup()
        except ServiceNotFoundError:
            return None

    @staticmethod
    def _controller_url(
        service: object, fallback_base: str, controller: str, *segments: object
    ) -> str:
        """Join an SDK controller's endpoint path onto its connector base URL.

        The versioned management path (``/v3/catalog`` and friends) differs per
        dataspace version, so it is read off the controller the SDK built rather
        than spelled out here. A service that does not expose the controller — a
        stub, or a version that dropped it — yields base URL plus segments.
        """
        controller_obj = getattr(service, controller, None)
        base = getattr(getattr(controller_obj, "adapter", None), "base_url", None)
        if not isinstance(base, str) or not base:
            base = fallback_base
        if not base:
            # No connector configured — a bare path would read as a real URL.
            return ""

        parts = [base.rstrip("/")]
        endpoint = getattr(controller_obj, "endpoint_url", None)
        if isinstance(endpoint, str):
            parts.append(endpoint.strip("/"))
        parts.extend(str(segment).strip("/") for segment in segments if segment is not None)
        return "/".join(part for part in parts if part)

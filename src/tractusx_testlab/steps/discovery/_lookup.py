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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The SDK's discovery services, built from ``infrastructure.engine.discovery``.

Testlab sends none of the discovery requests itself: the SDK's
``DiscoveryFinderService`` and ``ConnectorDiscoveryService`` do, and their HTTP
calls land in the step's trace through the SDK's own instrumentation. What is
here is only the wiring — the binding turned into the SDK's ``OAuth2Manager``
and services — and the SDK's failures named for the report.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from tractusx_sdk.dataspace.managers import OAuth2Manager
from tractusx_sdk.dataspace.services.discovery import (
    ConnectorDiscoveryService,
    DiscoveryFinderService,
)
from tractusx_sdk.industry.services.discovery import BpnDiscoveryService

from tractusx_testlab.logging.masking import register_secret
from tractusx_testlab.models import BoundServiceError, StepExecutionError
from tractusx_testlab.steps import sdk_call

if TYPE_CHECKING:
    from tractusx_testlab.models.domain.discovery_capability import DiscoveryBinding

__all__ = ["DiscoveryServices", "asked_url", "build_services", "call"]


class _NoToken:
    """The ``OAuth2Manager`` stand-in for discovery services that ask for no token.

    The SDK's services always ask their manager for a header; a finder bound
    without ``oauth2_auth_url`` — a mock, an open lab deployment — gets the headers
    back as they were.
    """

    connected = True

    def add_auth_header(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        return dict(headers or {})


class DiscoveryServices:
    """The Discovery Finder, and the SDK services that ask it, sharing one sign-in."""

    __slots__ = ("finder", "oauth")

    def __init__(self, finder: DiscoveryFinderService, oauth: OAuth2Manager | _NoToken) -> None:
        self.finder = finder
        self.oauth = oauth

    def connectors(self, discovery_type: str) -> ConnectorDiscoveryService:
        """The EDC Discovery the finder files under *discovery_type* (``bpn``)."""
        return ConnectorDiscoveryService(
            oauth=self.oauth,
            discovery_finder_service=self.finder,
            connector_discovery_key=discovery_type,
        )

    def bpns(self) -> BpnDiscoveryService:
        """The BPN Discovery, found through the finder per identifier type."""
        return BpnDiscoveryService(oauth=self.oauth, discovery_finder_service=self.finder)


def _sign_in(binding: DiscoveryBinding) -> OAuth2Manager | _NoToken:
    """The engine's technical user, signed in — or no one, when no IdP is bound."""
    if not binding.oauth2_auth_url:
        return _NoToken()
    return OAuth2Manager(
        auth_url=binding.oauth2_auth_url,
        realm=binding.oauth2_realm,
        clientid=binding.oauth2_client_id,
        clientsecret=binding.oauth2_client_secret,
    )


async def build_services(
    step_type: str, binding: DiscoveryBinding, finder_url: str, run: str
) -> DiscoveryServices:
    """Build the SDK services for *finder_url* with the binding's technical user.

    Built per step, not per run: the SDK caches a finder's answer for twelve
    hours, and a cache outliving the step would answer the next run from this
    one's dataspace.
    """
    if binding.oauth2_auth_url and not (binding.oauth2_realm and binding.oauth2_client_id):
        raise StepExecutionError(
            step_type,
            "infrastructure.engine.discovery.oauth2_auth_url is set but oauth2_realm or "
            "oauth2_client_id is not. The discovery services are reached with the engine's "
            "technical user; bind its oauth2_realm, oauth2_client_id and oauth2_client_secret, "
            "or leave oauth2_auth_url empty.",
        )
    if binding.oauth2_client_secret:
        register_secret(binding.oauth2_client_secret, run=run, explicit=True)
    # Signing in reads the IdP's well-known document: a network call, so off the loop.
    oauth = await call(
        step_type, f"the identity provider at {binding.oauth2_auth_url}", _sign_in, binding
    )
    return DiscoveryServices(DiscoveryFinderService(url=finder_url, oauth=oauth), oauth)


async def call[T](step_type: str, service: str, operation: Callable[..., T], *args: Any) -> T:
    """Run an SDK discovery *operation* off the loop, naming *service* when it fails.

    The SDK's discovery services report every failure — a refusal, an empty
    finder answer, an IdP that would not sign the client in — as a bare
    ``Exception`` with a sentence of its own. Left alone the runner reads that
    as a TestLab fault; it is the dataspace's service not doing its part.
    """
    try:
        return await sdk_call.run(operation, *args)
    except (StepExecutionError, BoundServiceError):
        raise
    except Exception as exc:  # the SDK raises bare Exception here
        raise BoundServiceError(f"{step_type}: {service} did not answer: {exc}") from exc


def asked_url(cache_status: dict[str, Any], key: str) -> str:
    """The service URL the SDK resolved through the finder for *key*, from its cache report."""
    for entry in cache_status.get("entries", []):
        if entry.get("key") == key:
            return str(entry.get("url") or "")
    return ""

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

"""The discovery capability: the dataspace's Discovery Finder, as the engine reaches it.

Kept beside :mod:`tractusx_testlab.models.domain.capabilities` rather than in
it: the connector and the registry are deployments a TCK provisions or tests,
while discovery is a dataspace service the engine only asks.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from tractusx_testlab.models.domain.capabilities import (
    OPERATOR_SUPPLIED,
    SECRET,
    CapabilityBinding,
)

__all__ = ["DiscoveryBinding"]


class DiscoveryBinding(CapabilityBinding):
    """The dataspace's discovery services, as the engine reaches them.

    A Catena-X consumer rarely starts from a connector address: it holds a
    business partner number and asks the dataspace where that partner's
    connector is. The question goes in two hops. The **Discovery Finder** is
    asked for the address of the discovery service of a key type — ``bpn``
    for the EDC Discovery — and that service is then asked for the BPN's
    connector endpoints. Only the first address is a deployment fact; the
    second is whatever the finder answers, so it is not bound here.

    The services are the dataspace's, not the system under test's, and they
    are reached with the engine's own technical user, which is why this is an
    engine-side capability. The fields are the SDK's own: ``oauth2_auth_url``,
    ``oauth2_realm``, ``oauth2_client_id`` and ``oauth2_client_secret`` build its ``OAuth2Manager``,
    and ``finder_url`` its ``DiscoveryFinderService``. Leaving ``oauth2_auth_url``
    empty reaches a finder — or a mock — that asks for no token.
    """

    identity_field: ClassVar[str] = "finder_url"
    credential_url_field: ClassVar[str] = "auth_url"

    finder_url: str = Field(
        default="",
        description=(
            "Search URL of the Discovery Finder, including its path — e.g. "
            "'https://discoveryfinder.example.com/api/v1.0/administration/connectors/discovery/search'."
        ),
        json_schema_extra=OPERATOR_SUPPLIED,
    )
    oauth2_auth_url: str = Field(
        default="",
        description=(
            "Root URL of the identity provider the engine's technical user signs in at — "
            "e.g. 'https://centralidp.example.com/auth/'. Empty when the discovery "
            "services ask for no token."
        ),
    )
    oauth2_realm: str = Field(
        default="",
        description="Realm of the technical user at 'oauth2_auth_url', e.g. 'CX-Central'.",
    )
    oauth2_client_id: str = Field(
        default="",
        description="Client ID of the engine's technical user.",
    )
    oauth2_client_secret: str = Field(
        default="",
        description=(
            "Client secret of the engine's technical user. A test reads it only as a "
            "handle, presentable to 'oauth2_auth_url' alone."
        ),
        json_schema_extra=SECRET,
        repr=False,
    )

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

"""What a standard and an ecosystem release mean for the services built from them.

A TCK says *which* standard and release it certifies against — ``CX-0018``,
``saturn`` — and the SDK needs *concrete wiring* for that: which connector
dialect to build, which AAS API path a registry answers on. Everything that
translates the one into the other lives here, so a new ecosystem release is a
table entry rather than a change spread across the seeder.

Two axes, deliberately kept apart:

- **Ecosystem release** (``saturn``, ``jupiter``) — the dataspace generation.
  It comes from the TCK's ``dataspace.version`` and it is what picks the SDK
  dialect. This is the axis that decides behaviour.
- **Standard** (``CX-0018`` at version ``2.1.3``) — what the capability
  certifies against. It comes from the TCK's ``infrastructure.<side>.<cap>.standard``
  block, is carried through to the bindings, and is reported rather than
  executed: it says what a run claims to prove.
"""

from __future__ import annotations

from tractusx_testlab.syntax import defaults

#: Ecosystem releases the engine knows how to wire. The SDK is the final
#: authority — it refuses an unsupported one when the service is built — but
#: knowing them here lets a typo be caught while the bindings are resolved.
KNOWN_RELEASES: tuple[str, ...] = ("saturn", "jupiter")

#: The standard each capability implements when the TCK names none (ADR-0019 §1).
#: ``submodel_server`` is deliberately absent: no standard id is assigned to it
#: in ADR-0019, and inventing one would put a claim in a run's report that
#: nothing backs.
CAPABILITY_STANDARDS: dict[str, str] = {
    "connector": "CX-0018",
    "dtr": "CX-0002",
}

#: AAS API path a registry answers on, per ecosystem release. Both current
#: releases serve v3.0; a release that moves the path adds a line here rather
#: than a branch in the seeder.
_AAS_API_PATHS: dict[str, str] = {
    "saturn": defaults.AAS_API_PATH,
    "jupiter": defaults.AAS_API_PATH,
}


def release_or_default(version: str) -> str:
    """Return the ecosystem release to build against, defaulting when unstated."""
    return (version or "").strip() or defaults.DATASPACE_VERSION


def is_known_release(version: str) -> bool:
    """Whether *version* names an ecosystem release the engine can wire."""
    return release_or_default(version) in KNOWN_RELEASES


def default_standard(capability: str) -> str:
    """Return the standard id a capability implements, or ``""`` if none is assigned."""
    return CAPABILITY_STANDARDS.get(capability, "")


def connector_dialect(version: str) -> str:
    """Return the ``dataspace_version`` the SDK builds a connector service for."""
    return release_or_default(version)


def aas_api_path(version: str) -> str:
    """Return the AAS API path a registry of this ecosystem release answers on."""
    return _AAS_API_PATHS.get(release_or_default(version), defaults.AAS_API_PATH)

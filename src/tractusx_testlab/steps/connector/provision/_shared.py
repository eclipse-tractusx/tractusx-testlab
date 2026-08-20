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

"""The pieces all three provisioning families share.

Reading an id off whatever the connector answered with, coercing a
``with:`` value that may arrive as a JSON string, and the create-or-409
dance — a provisioning step that is re-run against a connector that
already holds the resource is a pass, not a failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

#: HTTP status the connector answers with when the resource already exists.
_ALREADY_EXISTS = 409


def _as_id(value: Any, *keys: str) -> str:
    """Read an identifier that may arrive as a bare string or a prior step's output.

    Wiring ``${{ steps.create_policy.output }}`` into ``contract_policy_id`` passes
    the whole ``{"policy_id": …}`` object, so the id is picked out of it here
    rather than making every script unwrap it by hand.
    """
    if isinstance(value, dict):
        for key in (*keys, "@id"):
            found = value.get(key)
            if found:
                return str(found)
        return ""
    return str(value) if value else ""


def _config_object(value: Any, key: str) -> dict:
    """Read a config object that may arrive wrapped in the variable that holds it.

    Wiring ``${{ env.ccm_asset }}`` instead of ``${{ env.ccm_asset.asset }}``
    passes the whole variable, so the object is picked out of it here rather
    than making every script spell out the return key.
    """
    if not isinstance(value, dict):
        return {}
    inner = value.get(key)
    return inner if isinstance(inner, dict) else value


def _iri(value: Any) -> str | None:
    """Read an IRI that may be spelled bare or as a JSON-LD ``{"@id": …}``."""
    if isinstance(value, dict):
        value = value.get("@id")
    return str(value) if value else None


def _create_or_conflict(create, **kwargs) -> tuple[dict | None, int]:
    """Run a provider create call, treating a 409 as "already there, carry on"."""
    try:
        result = create(**kwargs)
    except ValueError as exc:
        if "409" in str(exc):
            return None, _ALREADY_EXISTS
        raise
    return result, 200

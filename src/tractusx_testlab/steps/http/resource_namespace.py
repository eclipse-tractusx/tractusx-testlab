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
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-6).
## It was reviewed and tested by a human committer.

"""Keep raw provisioning calls to the engine EDC in the player's namespace."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from tractusx_testlab.models import AuthoringError

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

EDC = "https://w3id.org/edc/v0.0.1/ns/"
COLLECTIONS = {"assets", "policydefinitions", "contractdefinitions"}


def _field(body: dict, key: str) -> Any:
    return body.get(key, body.get("edc:" + key, body.get(EDC + key)))


def require_resource_namespace(method: str, url: str, body: Any, context: StepContext) -> None:
    """Refuse raw engine resource creation that could escape this run's prefix.

    Generic HTTP keeps its wire body untouched. An author using it to provision
    EDC resources must supply scoped IDs and a scoped contract asset selector,
    just as the typed provider steps do automatically.
    """
    prefix = context.resource_prefix
    if not prefix or method.upper() != "POST":
        return
    management = context.infrastructure.engine.connector.management_url
    if not isinstance(management, str) or not management:
        return
    base = management.rstrip("/") + "/"
    if not url.startswith(base):
        return
    parts = urlsplit(url[len(base) :]).path.strip("/").split("/")
    if len(parts) != 2 or parts[0] not in {"v3", "v4alpha"} or parts[1] not in COLLECTIONS:
        return
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            body = None
    if not isinstance(body, dict):
        raise AuthoringError("EDC provisioning requires a JSON object with a run-scoped ID")

    def owns(value: Any) -> bool:
        return isinstance(value, str) and value.startswith(prefix)

    if not owns(body.get("@id") or _field(body, "id")):
        raise AuthoringError(
            "EDC resource IDs must use this run's execution.resource_prefix; "
            "use a connector/provider creation step or scope the raw HTTP body"
        )
    if parts[1] != "contractdefinitions":
        return
    if not all(owns(_field(body, key)) for key in ("accessPolicyId", "contractPolicyId")):
        raise AuthoringError("EDC contract definition policies must belong to this run")
    selectors = _field(body, "assetsSelector") or []
    if not isinstance(selectors, list) or not any(
        isinstance(selector, dict)
        and _field(selector, "operandLeft") in {EDC + "id", "edc:id", "id"}
        and _field(selector, "operator") in {"=", "like"}
        and owns(_field(selector, "operandRight"))
        for selector in selectors
    ):
        raise AuthoringError("EDC contract definition asset selectors must be scoped to this run")

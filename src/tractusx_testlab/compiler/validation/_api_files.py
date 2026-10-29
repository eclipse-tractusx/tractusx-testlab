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

"""Checking the API files a TCK carries (``env.apis``, ADR-0030).

Every entry is checked before anything is packed, and every problem is
reported at once, each naming the entry and the file: the file has to stay
inside ``apis/``, exist, and load — parse as its declared type, be OpenAPI
3.0.x / 3.1.x, and resolve every ``$ref`` inside itself
(:func:`~tractusx_testlab.openapi.load_api_document`). Nothing is fetched.

A document that loads is cached, so the IR builder and a player in the same
process read it without parsing it again.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from tractusx_testlab.models.authoring.env_files import ApiDefinition
from tractusx_testlab.openapi import ApiDocumentError, load_api_document
from tractusx_testlab.player.loading._package_paths import UnsafePackagePathError, package_path

#: The folder API files live in, and the collection under ``env:`` naming them.
APIS = "apis"


def api_file_findings(env: dict[str, Any], base_dir: Path) -> list[str]:
    """Every problem with the manifest's ``env.apis`` entries and their files."""
    entries = env.get(APIS)
    if not isinstance(entries, list):
        return []
    apis = [_definition(entry) for entry in entries]
    declared = [api for api in apis if api is not None]
    findings = [
        f"env.apis: id '{api_id}' is declared {count} times; each API needs its own id."
        for api_id, count in Counter(api.id for api in declared).items()
        if count > 1
    ]
    if _declares_variable(env, APIS) and declared:
        findings.append(
            "env.variables: a variable may not be called 'apis' while env.apis is declared; "
            "'${{ env.apis.<id> }}' names an API file."
        )
    for api in declared:
        findings.extend(_file_findings(api, base_dir))
    return findings


def _definition(entry: Any) -> ApiDefinition | None:
    """The entry as a model, or ``None`` when the manifest's model check reports it."""
    try:
        return ApiDefinition.model_validate(entry)
    except ValidationError:
        return None


def _declares_variable(env: dict[str, Any], name: str) -> bool:
    variables = env.get("variables")
    return isinstance(variables, list) and any(
        isinstance(entry, dict) and entry.get("id") == name for entry in variables
    )


def _file_findings(api: ApiDefinition, base_dir: Path) -> list[str]:
    label = f"API file {APIS}/{api.source} (env.apis[{api.id}])"
    try:
        path = package_path(base_dir / APIS, api.source)
    except UnsafePackagePathError as exc:
        return [f"{label} must name a file inside {APIS}/: {exc}"]
    if not path.is_file():
        return [f"{label} not found."]
    try:
        # `type` is always set once the model has validated (inferred if omitted).
        load_api_document(path, str(api.type))
    except ApiDocumentError as exc:
        return [f"{label} {problem}." for problem in exc.problems]
    return []

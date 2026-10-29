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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Asset builders — the IR's references to package files, and the manifest's entries for them.

A package carries three folders of files its ``env:`` block names:
``schemas/``, ``testdata/`` and ``apis/`` (ADR-0030). The IR refers to each
file by id (``{id: {asset_key, type}}``); the manifest lists each with its
digest, size and media type.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tractusx_testlab.compiler.ir._instructions import (
    compute_source_hash,
    infer_testdata_type,
)
from tractusx_testlab.models.authoring.env_files import ApiDefinition

logger = logging.getLogger(__name__)

#: The package folders a compiled package copies under ``assets/``.
ASSET_FOLDERS = ("schemas", "testdata", "apis")


def build_schema_refs(env_raw: dict[str, Any]) -> dict[str, Any]:
    """The IR's ``schemas`` block: each JSON Schema file by id."""
    schemas_raw = env_raw.get("schemas", {})
    if isinstance(schemas_raw, list):
        return {
            entry.get("id", ""): {"asset_key": entry.get("source", ""), "type": "application/json"}
            for entry in schemas_raw
        }
    return {
        name: {"asset_key": schema.get("file", ""), "type": "application/json"}
        for name, schema in schemas_raw.items()
    }


def build_testdata_refs(env_raw: dict[str, Any]) -> dict[str, Any]:
    """The IR's ``testdata`` block: each test data file by id, with its media type."""
    testdata_raw = env_raw.get("testdata", {})
    if isinstance(testdata_raw, list):
        return {
            entry.get("id", ""): {
                "asset_key": entry.get("source", ""),
                "type": entry.get("type", infer_testdata_type(entry.get("source", ""))),
            }
            for entry in testdata_raw
        }
    return {
        name: {"asset_key": td.get("file", ""), "type": infer_testdata_type(td.get("file", ""))}
        for name, td in testdata_raw.items()
    }


def build_api_refs(env_raw: dict[str, Any]) -> dict[str, Any]:
    """The IR's ``apis`` block: each API file by id, with its declared or inferred type."""
    apis = [ApiDefinition.model_validate(entry) for entry in env_raw.get("apis") or []]
    return {api.id: {"asset_key": api.source, "type": api.type} for api in apis}


def build_asset_entries(
    base_dir: Path, folder_name: str, assets_dict: dict[str, Any]
) -> list[dict[str, str | int]]:
    """Build enriched asset entries with id, path, digest, size, mediaType, and location."""
    entries: list[dict[str, str | int]] = []
    for asset_id, entry in assets_dict.items():
        asset_key = entry.get("asset_key")
        if not asset_key:
            continue
        file_path = base_dir / folder_name / asset_key
        if not file_path.is_file():
            logger.warning("Asset file not found, skipping: %s", file_path)
            continue
        mime = _media_type(folder_name, asset_key, entry)
        entries.append(
            {
                "id": asset_id,
                "file": asset_key,
                "path": f"assets/{folder_name}/{asset_key}",
                "digest": compute_source_hash(file_path),
                "size": file_path.stat().st_size,
                "mediaType": mime,
                "location": "filesystem",
            }
        )
    return entries


def _media_type(folder_name: str, asset_key: str, entry: dict[str, Any]) -> str:
    """The media type a file of *folder_name* is listed with in the manifest."""
    if folder_name == "schemas":
        return "application/json"
    if folder_name == "apis":
        return str(entry["type"])
    return infer_testdata_type(asset_key)

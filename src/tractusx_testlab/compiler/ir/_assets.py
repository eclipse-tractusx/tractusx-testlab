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

"""Asset entry builders — enriched manifest asset metadata."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tractusx_testlab.compiler.ir._instructions import (
    compute_source_hash,
    infer_testdata_type,
)

logger = logging.getLogger(__name__)


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
        mime = "application/json" if folder_name == "schemas" else infer_testdata_type(asset_key)
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

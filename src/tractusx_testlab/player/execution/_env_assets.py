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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The files a TCK's ``env`` block points at, bound into a run's context.

``env.testdata`` and ``env.schemas`` entries are JSON files seeded as templates
under ``<folder>.<id>`` and ``env.<folder>.<id>``; ``env.apis`` entries are
OpenAPI documents bound read-only under ``apis.<id>`` (ADR-0030). Split from
:mod:`._context_seeder`, which seeds the variables, so each module keeps one
responsibility.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tractusx_testlab.openapi import ApiDocumentError, BoundApiDocument, load_api_document
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.loading._package_paths import package_path

logger = logging.getLogger(__name__)


def load_env_assets(context: StepContext, tck: Any) -> None:
    """Bind the test data, schema and API files the TCK's ``env`` block declares."""
    _load_testdata(context, tck)
    _load_schemas(context, tck)
    _load_apis(context, tck)


def _resolve_asset_path(base_dir: Path, folder_name: str, source: str) -> Path | None:
    """Locate an asset file under *folder_name*, tolerating both package layouts.

    A compiled ``.tck`` archive stores assets under ``assets/<folder>/`` while a
    raw authoring directory keeps them in a top-level ``<folder>/``.  Both are
    valid inputs to the player, so try the compiled layout first and fall back
    to the raw one.  Returns ``None`` when the file exists in neither.
    """
    # `source` comes from the package; it may not name a file outside it.
    for candidate in (
        package_path(base_dir, f"assets/{folder_name}/{source}"),
        package_path(base_dir, f"{folder_name}/{source}"),
    ):
        if candidate.is_file():
            return candidate
    return None


def _load_json_assets(
    context: StepContext,
    tck: Any,
    folder_name: str,
    entries: Any,
) -> None:
    """Load JSON assets from *folder_name* and seed them under ``<folder>.<id>``.

    Each asset is bound to both ``<folder>.<id>`` and ``env.<folder>.<id>`` so
    that ``${{ env.<folder>.<id> }}`` and the bare ``${{ <folder>.<id> }}`` form
    both resolve.
    """
    for entry in entries:
        path = _resolve_asset_path(tck.base_dir, folder_name, entry.source)
        if path is None:
            logger.warning(
                "%s file not found, skipping: %s/%s (searched under %s)",
                folder_name.capitalize(),
                folder_name,
                entry.source,
                tck.base_dir,
            )
            continue
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load %s file %s: %s", folder_name, path, exc)
            continue
        context.set_template(f"{folder_name}.{entry.id}", content)
        context.set_template(f"env.{folder_name}.{entry.id}", content)
        logger.debug("Loaded %s '%s' from %s", folder_name, entry.id, path.name)


def _load_testdata(context: StepContext, tck: Any) -> None:
    """Seed context with testdata files declared in the TCK ``env.testdata`` block."""
    env_def = getattr(tck.definition, "env", None)
    _load_json_assets(context, tck, "testdata", getattr(env_def, "testdata", None) or [])


def _load_schemas(context: StepContext, tck: Any) -> None:
    """Seed context with JSON Schema files declared in the TCK ``env.schemas`` block."""
    env_def = getattr(tck.definition, "env", None)
    _load_json_assets(context, tck, "schemas", getattr(env_def, "schemas", None) or [])


def _load_apis(context: StepContext, tck: Any) -> None:
    """Bind each ``env.apis`` document for ``${{ env.apis.<id> }}`` (ADR-0030).

    Under ``apis.<id>``, read-only and tagged with its id and digest
    (:class:`BoundApiDocument`); as data, not as a template — a ``${{`` in the
    document is not a reference the author wrote. A file the compiler would
    have refused is logged and left unbound: a step naming it fails unresolved.
    """
    env_def = getattr(tck.definition, "env", None)
    for api in getattr(env_def, "apis", None) or []:
        path = _resolve_asset_path(tck.base_dir, "apis", api.source)
        try:
            if path is None:
                raise ApiDocumentError(["is not in the package"])
            document = load_api_document(path, str(api.type))
        except ApiDocumentError as exc:
            logger.error("API file apis/%s (env.apis[%s]) %s", api.source, api.id, exc)
            continue
        bound = BoundApiDocument(document.content, api.id, document.sha256)
        context.set_variable(f"apis.{api.id}", bound)

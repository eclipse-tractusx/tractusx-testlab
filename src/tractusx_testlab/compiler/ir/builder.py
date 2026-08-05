#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""IR Builder — compiles TCK manifests into manifest.yaml + tck-execution.json."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from tractusx_testlab.compiler.validation._expressions import resolve_expression
from tractusx_testlab.compiler._fingerprint import build_fingerprint
from tractusx_testlab.compiler.ir._assets import build_asset_entries
from tractusx_testlab.compiler.ir._compilation import build_compiled_tests
from tractusx_testlab.compiler.ir._helpers import (
    _infer_type, compute_source_hash,
    infer_testdata_type as _infer_testdata_type,
)
from tractusx_testlab.compiler.ir._symbols import build_global_symbols
from tractusx_testlab.compiler.validation._rules import validate_tck_manifest

logger = logging.getLogger(__name__)

def build_ir(
    manifest_path: Path,
    output_path: Optional[Path] = None,
    version: Optional[str] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build manifest and execution payload from a TCK manifest.

    Returns:
        Tuple of (manifest_dict, execution_dict).
    """
    manifest_data = _load_manifest(manifest_path)
    base_dir = manifest_path.parent

    # Validate manifest and test files against JSON schemas
    validate_tck_manifest(manifest_data, base_dir)

    compiler_version = version or "0.5.0"
    compiled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    testlab = manifest_data.get("testlab", "v1-alpha")
    tck_id = manifest_data.get("id", manifest_path.stem)

    tests_list = _build_tests_list(manifest_data, base_dir)
    compiled_tests = build_compiled_tests(manifest_data, base_dir)
    env_raw = manifest_data.get("env", {})
    global_symbols = build_global_symbols(env_raw)
    services = _build_services(env_raw)
    schemas = _build_schemas(env_raw)
    testdata = _build_testdata(env_raw)

    execution_dict: dict[str, Any] = {
        "global_symbols": global_symbols,
        "services": services,
        "schemas": schemas,
        "testdata": testdata,
        "tests": tests_list,
        "compiled_tests": compiled_tests,
    }

    # Build grouped manifest
    metadata = manifest_data.get("metadata", {})
    tck_section: dict[str, Any] = {
        "id": tck_id,
    }
    if metadata:
        tck_section["metadata"] = metadata

    execution_json = json.dumps(execution_dict, indent=2, ensure_ascii=False)
    execution_json_bytes = execution_json.encode("utf-8")
    fingerprint = build_fingerprint(execution_json_bytes)

    schema_assets = build_asset_entries(base_dir, "schemas", schemas)
    testdata_assets = build_asset_entries(base_dir, "testdata", testdata)

    manifest_dict: dict[str, Any] = {
        "kind": "manifest",
        "package": {
            "format": "tck",
            "format_version": "1.0.0",
            "testlab": testlab,
        },
        "tck": tck_section,
        "compilation": {
            "compiled_at": compiled_at,
            "compiler_version": compiler_version,
            "fingerprint": fingerprint,
        },
        "tests": tests_list,
        "assets": {
            "schemas": schema_assets,
            "testdata": testdata_assets,
        },
    }

    all_asset_entries = schema_assets + testdata_assets
    package_checksum = _compute_package_checksum(
        manifest_dict, execution_json_bytes, all_asset_entries,
    )
    manifest_dict["package"]["checksum"] = package_checksum
    logger.info("Package checksum: %s", package_checksum)

    if output_path:
        output_path.mkdir(parents=True, exist_ok=True)
        manifest_file = output_path / "manifest.yaml"
        manifest_file.write_text(
            yaml.dump(manifest_dict, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        execution_file = output_path / "tck-execution.json"
        execution_file.write_text(execution_json, encoding="utf-8")
        _copy_assets(base_dir, output_path)
        logger.info("Compiled %d tests to %s", len(compiled_tests), output_path)

    return manifest_dict, execution_dict


def _compute_package_checksum(
    manifest_dict: dict[str, Any],
    execution_json_bytes: bytes,
    asset_entries: list[dict[str, Any]],
) -> str:
    """Compute blake2b-256 package checksum from manifest + execution + asset digests.

    Uses already-computed per-asset digests (Merkle-like) instead of re-reading files.
    """
    manifest_copy = {**manifest_dict, "package": {**manifest_dict["package"], "checksum": ""}}
    manifest_bytes = yaml.dump(
        manifest_copy, default_flow_style=False, sort_keys=False,
    ).encode("utf-8")

    asset_digest_bytes = "".join(
        entry["digest"] for entry in sorted(asset_entries, key=lambda e: e["path"])
    ).encode("utf-8")

    content = manifest_bytes + execution_json_bytes + asset_digest_bytes
    return f"blake2b:{hashlib.blake2b(content, digest_size=32).hexdigest()}"


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and validate the TCK manifest YAML."""
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at top level in {manifest_path}")
    return data


def _copy_assets(base_dir: Path, output_path: Path) -> None:
    """Copy schemas/ and testdata/ from the source TCK into output/assets/."""
    assets_dir = output_path / "assets"
    for folder_name in ("schemas", "testdata"):
        src_folder = base_dir / folder_name
        if not src_folder.is_dir():
            continue
        dest_folder = assets_dir / folder_name
        if dest_folder.exists():
            shutil.rmtree(dest_folder)
        shutil.copytree(src_folder, dest_folder)
        logger.info("Copied %s to %s", src_folder, dest_folder)


def _build_services(env_raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the root-level services list (instantiation recipes)."""
    services_raw = env_raw.get("services", [])
    return [_build_service_entry(svc) for svc in services_raw]


def _build_schemas(env_raw: dict[str, Any]) -> dict[str, Any]:
    """Build the root-level schemas dict (asset references)."""
    schemas_raw = env_raw.get("schemas", {})
    if isinstance(schemas_raw, list):
        return {
            entry.get("id", ""): {
                "asset_key": entry.get("source", ""),
                "type": "application/json",
            }
            for entry in schemas_raw
        }
    return {
        name: {"asset_key": schema.get("file", ""), "type": "application/json"}
        for name, schema in schemas_raw.items()
    }


def _build_testdata(env_raw: dict[str, Any]) -> dict[str, Any]:
    """Build the root-level testdata dict (asset references)."""
    testdata_raw = env_raw.get("testdata", {})
    if isinstance(testdata_raw, list):
        return {
            entry.get("id", ""): {
                "asset_key": entry.get("source", ""),
                "type": entry.get("type", _infer_testdata_type(entry.get("source", ""))),
            }
            for entry in testdata_raw
        }
    return {
        name: {
            "asset_key": td.get("file", ""),
            "type": _infer_testdata_type(td.get("file", "")),
        }
        for name, td in testdata_raw.items()
    }


def _build_service_entry(svc: dict[str, Any]) -> dict[str, Any]:
    """Build a single service entry for the IR env block."""
    entry: dict[str, Any] = {"name": svc.get("name", ""), "uses": svc.get("uses", "")}
    if with_block := svc.get("with", {}):
        entry["with"] = resolve_expression(with_block)
    return entry


def _build_tests_list(
    manifest_data: dict[str, Any], base_dir: Path,
) -> list[dict[str, Any]]:
    """Build the tests reference list with source hashes."""
    from tractusx_testlab.compiler.ir._helpers import (
        compute_source_hash,
        load_test_file,
        resolve_test_path,
    )

    tests_raw = manifest_data.get("tests", [])
    tests_list: list[dict[str, Any]] = []

    for entry in tests_raw:
        file_ref = entry if isinstance(entry, str) else entry.get(
            "test", entry.get("file", entry.get("id", ""))
        )
        test_path = resolve_test_path(file_ref, base_dir)
        test_data = load_test_file(test_path)
        source_hash = compute_source_hash(test_path)

        tests_list.append({
            "id": test_data.get("id", test_path.stem),
            "source_hash": source_hash,
        })

    return tests_list



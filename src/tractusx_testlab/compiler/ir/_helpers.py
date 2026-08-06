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

"""IR Builder helpers — instruction compilation and symbol table construction."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from tractusx_testlab.compiler.validation._expressions import resolve_expression


def build_instructions(
    test_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build the flattened instructions list and collect step symbols.

    Returns:
        (instructions, step_symbols) where step_symbols is a list of
        {id, field, type, class, produced_by, source} dicts.
    """
    setup_steps = test_data.get("setup", [])
    main_steps = test_data.get("execution", [])
    teardown_steps = test_data.get("teardown", [])

    instructions: list[dict[str, Any]] = []
    step_symbols: list[dict[str, Any]] = []
    global_index = 0

    for phase, steps in [("setup", setup_steps), ("main", main_steps), ("teardown", teardown_steps)]:
        for phase_index, step in enumerate(steps):
            instruction = _build_instruction(step, global_index, phase, phase_index)
            instructions.append(instruction)

            source = _source_for_phase(phase)
            _collect_step_symbols(step, global_index, source, step_symbols)

            global_index += 1

    return instructions, step_symbols


def _source_for_phase(phase: str) -> str:
    """Map a phase name to the symbol source label."""
    if phase == "setup":
        return "setup_output"
    if phase == "teardown":
        return "teardown_output"
    return "step_output"


def _collect_step_symbols(
    step: dict[str, Any], global_index: int, source: str,
    step_symbols: list[dict[str, Any]],
) -> None:
    """Collect output symbols from a step definition."""
    returns = step.get("returns", {})
    for field_name, field_def in returns.items():
        step_symbols.append({
            "id": step.get("id", ""),
            "field": field_name,
            "type": field_def.get("type", "string") if isinstance(field_def, dict) else "string",
            "class": field_def.get("class", "") if isinstance(field_def, dict) else "",
            "produced_by": global_index,
            "source": source,
        })


def _build_instruction(
    step: dict[str, Any], index: int, phase: str, phase_index: int,
) -> dict[str, Any]:
    """Build a single instruction entry from a step definition."""
    with_block = step.get("with", {})
    resolved_with = resolve_expression(with_block)

    returns = step.get("returns", {})
    resolved_returns: dict[str, Any] = {}
    for field_name, field_def in returns.items():
        if isinstance(field_def, dict):
            resolved_returns[field_name] = {
                k: v for k, v in field_def.items()
                if k in ("type", "class")
            }
        else:
            resolved_returns[field_name] = {"type": "string"}

    validate = _build_validate_block(step)
    on_failure = "continue" if phase == "teardown" else step.get("on_failure", "abort")

    return {
        "index": index,
        "id": step.get("id", ""),
        "uses": step.get("uses", ""),
        "name": step.get("name", ""),
        "with": resolved_with,
        "returns": resolved_returns,
        "validate": validate,
        "phase": phase,
        "phase_index": phase_index,
        "on_failure": on_failure,
    }


def _build_validate_block(step: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the validate array from step's validate block or inline assertion."""
    validate_raw = step.get("validate", [])
    validations: list[dict[str, Any]] = [
        {"uses": v.get("uses", "validate/assert"), "with": resolve_expression(v.get("with", {}))}
        for v in validate_raw
    ]
    # For assert steps, also include the step itself as a validation
    uses = step.get("uses", "")
    if uses.startswith("validate/") and not validate_raw:
        validations.append({"uses": uses, "with": resolve_expression(step.get("with", {}))})

    return validations


def resolve_test_path(file_ref: str, base_dir: Path) -> Path:
    """Resolve a test file reference to an absolute path."""
    test_path = base_dir / file_ref
    if test_path.exists():
        return test_path
    test_path = base_dir / "tests" / file_ref
    if test_path.exists():
        return test_path
    raise FileNotFoundError(f"Referenced test file not found: {file_ref}")


def load_test_file(test_path: Path) -> dict[str, Any]:
    """Load a test YAML file."""
    with open(test_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {test_path}")
    return data


def compute_source_hash(path: Path) -> str:
    """Compute blake2b-256 hash of a file's contents."""
    content = path.read_bytes()
    digest = hashlib.blake2b(content, digest_size=32).hexdigest()
    return f"blake2b:{digest}"


def _infer_type(value: Any) -> str:
    """Infer the IR type string from a Python value."""
    match value:
        case bool(): return "boolean"
        case int(): return "integer"
        case float(): return "number"
        case list(): return "array"
        case dict(): return "object"
        case _: return "string"


def infer_testdata_type(filename: str) -> str:
    """Infer MIME type from a testdata filename."""
    ext_map = {".json": "application/json", ".pdf": "application/pdf", ".xml": "application/xml"}
    return ext_map.get(Path(filename).suffix, "application/octet-stream")

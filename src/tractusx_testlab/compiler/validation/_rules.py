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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""TCK manifest and test file validation against JSON schemas."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

logger = logging.getLogger(__name__)

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def _load_schema(schema_name: str) -> dict[str, Any]:
    """Load a JSON schema from the schemas directory."""
    schema_path = _SCHEMAS_DIR / schema_name
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _collect_errors(
    validator: Draft202012Validator,
    data: dict[str, Any],
    source_label: str,
) -> list[str]:
    """Collect all validation errors with human-readable messages."""
    errors: list[str] = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else ""
        if path:
            location = f"'{path}' in {source_label}"
        else:
            location = source_label
        errors.append(f"{error.message} (at {location})")
    return errors


def validate_tck_manifest(
    manifest_data: dict[str, Any],
    base_dir: Path,
) -> None:
    """Validate TCK manifest and all referenced test files.

    Raises:
        ValueError: If validation errors are found. Message lists ALL errors.
    """
    all_errors: list[str] = []

    # Validate the index manifest
    index_schema = _load_schema("tck_index.schema.json")
    index_validator = Draft202012Validator(index_schema)
    all_errors.extend(_collect_errors(index_validator, manifest_data, "index.yaml"))

    # Validate referenced file existence
    all_errors.extend(_validate_file_refs(manifest_data, base_dir))

    # Validate variable scope annotations
    env = manifest_data.get("env") or {}
    all_errors.extend(_validate_variable_scopes(env))

    # Validate that every scoped variable has a side that exists to be asked
    all_errors.extend(
        _validate_scoped_sides_are_declared(env, manifest_data.get("infrastructure"))
    )

    # Validate each test file
    tests = manifest_data.get("tests", [])
    test_schema = _load_schema("tck_test.schema.json")
    test_validator = Draft202012Validator(test_schema)

    for test_entry in tests:
        test_file = test_entry if isinstance(test_entry, str) else test_entry.get(
            "file", test_entry.get("id", "")
        )
        if not test_file:
            continue
        test_path = base_dir / "tests" / test_file
        if not test_path.is_file():
            all_errors.append(f"Referenced test file not found: tests/{test_file}")
            continue
        test_data = yaml.safe_load(test_path.read_text(encoding="utf-8"))
        if not isinstance(test_data, dict):
            all_errors.append(f"Test file 'tests/{test_file}' is not a valid YAML mapping")
            continue
        all_errors.extend(
            _collect_errors(test_validator, test_data, f"tests/{test_file}")
        )
        all_errors.extend(
            _reject_deprecated_verbs(test_data, f"tests/{test_file}")
        )
        all_errors.extend(
            _reject_validate_step(test_data, f"tests/{test_file}")
        )

    if all_errors:
        error_list = "\n  - ".join(all_errors)
        raise ValueError(
            f"TCK validation failed with {len(all_errors)} error(s):\n  - {error_list}"
        )

    logger.info("TCK manifest validation passed")


_VALID_SCOPES: frozenset[str] = frozenset({"engine", "sut"})


def _validate_variable_scopes(env_data: dict[str, Any]) -> list[str]:
    """Validate that every ``source: input`` variable declares a valid scope.

    Variables with ``source: value`` or ``source: generated`` are exempt.
    """
    errors: list[str] = []
    variables = env_data.get("variables") or []
    if not isinstance(variables, list):
        return errors
    for entry in variables:
        if not isinstance(entry, dict):
            continue
        with_block = entry.get("with") or {}
        if str(with_block.get("source", "")) != "input":
            continue
        var_id = entry.get("id", "?")
        scope = with_block.get("scope")
        if scope is None:
            errors.append(
                f"Variable '{var_id}' has source: input but no scope declared. "
                f"Add scope: engine or scope: sut to identify who is responsible "
                f"for providing this value at runtime."
            )
        elif scope not in _VALID_SCOPES:
            errors.append(
                f"Variable '{var_id}' has an unrecognized scope: '{scope}'. "
                f"Valid values are: engine, sut."
            )
    return errors


def _scoped_input_variables(env_data: dict[str, Any]) -> list[tuple[str, str]]:
    """Return every ``(variable id, scope)`` pair the env block requests."""
    variables = env_data.get("variables") or []
    if not isinstance(variables, list):
        return []
    pairs: list[tuple[str, str]] = []
    for entry in variables:
        if not isinstance(entry, dict):
            continue
        with_block = entry.get("with") or {}
        if str(with_block.get("source", "")) != "input":
            continue
        scope = with_block.get("scope")
        if scope in _VALID_SCOPES:
            pairs.append((str(entry.get("id", "?")), str(scope)))
    return pairs


def _sides_with_a_required_capability(infrastructure: Any) -> set[str]:
    """Return the sides that declare at least one ``required: true`` capability.

    A side is only real when something is required of it. Declaring
    ``sut: {connector: {required: false}}`` describes a capability the run does
    not need, which is not a system anyone can be asked for a value.
    """
    if not isinstance(infrastructure, dict):
        return set()
    sides: set[str] = set()
    for side, capabilities in infrastructure.items():
        if not isinstance(capabilities, dict):
            continue
        for requirement in capabilities.values():
            if isinstance(requirement, dict) and requirement.get("required") is True:
                sides.add(str(side))
                break
    return sides


def _validate_scoped_sides_are_declared(
    env_data: dict[str, Any],
    infrastructure: Any,
) -> list[str]:
    """Reject a variable scoped to a side the ``infrastructure:`` block never declares.

    ``scope: sut`` means "the operator of the system under test supplies this
    when the run starts". If nothing is required of the SUT, there is no such
    system in this TCK and therefore no operator to ask — the variable would sit
    on the run-start form with no owner, and whatever the run then did with the
    empty value would fail far from here.

    The check is deliberately per-SIDE rather than per-capability: which
    capability a given variable belongs to is not recoverable from the manifest,
    so demanding it would mean inventing a name-to-capability registry that the
    author could not see or extend. A side declaring nothing at all is the
    unambiguous case, and it is the one that actually gets authored.

    Skipped entirely when no TCK-level ``infrastructure:`` block is present AND
    no variable is scoped, since per-script blocks then govern the run.
    """
    scoped = _scoped_input_variables(env_data)
    if not scoped:
        return []

    declared_sides = _sides_with_a_required_capability(infrastructure)
    errors: list[str] = []
    for var_id, scope in scoped:
        if scope in declared_sides:
            continue
        errors.append(
            f"Variable '{var_id}' is scoped to '{scope}', but the infrastructure "
            f"block requires no {scope} capability. Declare what the run needs "
            f"(e.g. infrastructure.{scope}.connector.required: true), or remove "
            f"the variable."
        )
    return errors


def _validate_file_refs(
    manifest_data: dict[str, Any],
    base_dir: Path,
) -> list[str]:
    """Validate that all referenced schema and testdata files exist."""
    errors: list[str] = []
    env = manifest_data.get("env", {})

    schemas = env.get("schemas", {})
    if isinstance(schemas, list):
        for entry in schemas:
            source = entry.get("source") if isinstance(entry, dict) else None
            if source:
                path = base_dir / "schemas" / source
                if not path.is_file():
                    errors.append(
                        f"Referenced schema file not found: schemas/{source} "
                        f"(env.schemas[{entry.get('id', '?')}])"
                    )
    elif isinstance(schemas, dict):
        for name, entry in schemas.items():
            if isinstance(entry, dict) and "file" in entry:
                path = base_dir / "schemas" / entry["file"]
                if not path.is_file():
                    errors.append(
                        f"Referenced schema file not found: schemas/{entry['file']} "
                        f"(env.schemas.{name})"
                    )

    testdata = env.get("testdata", {})
    if isinstance(testdata, list):
        for entry in testdata:
            source = entry.get("source") if isinstance(entry, dict) else None
            if source:
                path = base_dir / "testdata" / source
                if not path.is_file():
                    errors.append(
                        f"Referenced testdata file not found: testdata/{source} "
                        f"(env.testdata[{entry.get('id', '?')}])"
                    )
    elif isinstance(testdata, dict):
        for name, entry in testdata.items():
            if isinstance(entry, dict) and "file" in entry:
                path = base_dir / "testdata" / entry["file"]
                if not path.is_file():
                    errors.append(
                        f"Referenced testdata file not found: testdata/{entry['file']} "
                        f"(env.testdata.{name})"
                    )

    return errors


_DEPRECATED_VERB_PREFIXES = ("precondition/",)


def _reject_deprecated_verbs(
    test_data: dict[str, Any],
    source_label: str,
) -> list[str]:
    """Reject steps that use deprecated verb prefixes (ADR-0021)."""
    errors: list[str] = []
    for phase in ("setup", "execution", "teardown"):
        steps = test_data.get(phase, [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "")
            for prefix in _DEPRECATED_VERB_PREFIXES:
                if uses.startswith(prefix):
                    step_id = step.get("id", "?")
                    errors.append(
                        f"Rejected step '{step_id}' in {source_label}: "
                        f"'{uses}' is no longer accepted (removed by ADR-0021). "
                        f"Migrate to a complex variable in env.variables with "
                        f"'uses: config/connector/policy'."
                    )
    return errors

def _reject_validate_step(
    test_data: dict[str, Any],
    source_label: str,
) -> list[str]:
    """Reject steps that use deprecated verb prefixes (ADR-0021)."""
    errors: list[str] = []
    for phase in ("setup", "execution", "teardown"):
        steps = test_data.get(phase, [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses", "")
            if uses.startswith("validate/"):
                step_id = step.get("id", "?")
                errors.append(
                    f"Rejected step '{step_id}' in {source_label}: "
                    f"'{uses}' cannot be used as a standalone step. "
                    "Place it under the parent step's 'validate:' block."
                )
    return errors

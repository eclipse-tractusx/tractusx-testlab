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

"""TCK manifest and test file validation against JSON schemas.

Everything a TCK must satisfy beyond its JSON schema is a rule returning the
errors it found, and the rules that repeat over a vocabulary — the ``uses:``
prefixes a script may no longer name, the ``env:`` collections whose entries
name a file — are tables walked once rather than a loop written per entry.
Every rule runs; nothing short-circuits, so an author sees every problem in the
TCK at once instead of one per compile.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tractusx_testlab.compiler.validation._variable_declarations import (
    declared_variable_ids,
    validate_variable_declarations,
    validate_variable_references,
)
from tractusx_testlab.compiler.validation.json_schema_findings import collect_errors, validator_for
from tractusx_testlab.syntax import diagnostics

logger = logging.getLogger(__name__)

#: The phases a step can sit in; a rule about steps means all three.
_PHASES = ("setup", "execution", "teardown")


def validate_tck_manifest(
    manifest_data: dict[str, Any],
    base_dir: Path,
) -> None:
    """Validate TCK manifest and all referenced test files.

    Raises:
        ValueError: If validation errors are found. Message lists ALL errors.
    """
    env = manifest_data.get("env") or {}

    all_errors: list[str] = [
        *collect_errors(validator_for("tck_index.schema.json"), manifest_data, "index.yaml"),
        *_validate_file_refs(manifest_data, base_dir),
        *validate_variable_declarations(env),
        *_validate_variable_scopes(env),
        *_validate_scoped_sides_are_declared(env, manifest_data.get("infrastructure")),
    ]

    variable_ids = declared_variable_ids(env)
    for test_file in _referenced_test_files(manifest_data):
        label = f"tests/{test_file}"
        test_path = base_dir / "tests" / test_file
        if not test_path.is_file():
            all_errors.append(f"Referenced test file not found: {label}")
            continue
        try:
            test_data = yaml.safe_load(test_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            all_errors.append(str(diagnostics.unparseable(exc, test_path)))
            continue
        if not isinstance(test_data, dict):
            all_errors.append(f"Test file '{label}' is not a valid YAML mapping")
            continue
        all_errors.extend(error for rule in _TEST_FILE_RULES for error in rule(test_data, label))
        all_errors.extend(validate_variable_references(test_data, variable_ids, label))

    if all_errors:
        error_list = "\n  - ".join(all_errors)
        raise ValueError(
            f"TCK validation failed with {len(all_errors)} error(s):\n  - {error_list}"
        )

    logger.info("TCK manifest validation passed")


def _referenced_test_files(manifest_data: dict[str, Any]) -> Iterator[str]:
    """Yield the file name of every test the manifest lists.

    One spelling: an entry is a mapping and ``id`` is the file under ``tests/``.
    Anything else is already reported by the schema check that runs alongside
    this one, so it is passed over here rather than guessed at.
    """
    for entry in manifest_data.get("tests", []):
        if isinstance(entry, dict) and (name := entry.get("id")):
            yield str(name)


_VALID_SCOPES: frozenset[str] = frozenset({"engine", "sut"})


def _validate_variable_scopes(env_data: dict[str, Any]) -> list[str]:
    """Validate that every ``source: input`` variable declares a valid scope.

    Variables with ``source: value`` or ``source: generated`` are exempt.
    """
    errors: list[str] = []
    for entry in _input_variables(env_data):
        var_id = entry.get("id", "?")
        scope = (entry.get("with") or {}).get("scope")
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


def _input_variables(env_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every ``env.variables`` entry that asks for a value at run start."""
    variables = env_data.get("variables") or []
    if not isinstance(variables, list):
        return
    for entry in variables:
        if not isinstance(entry, dict):
            continue
        if str((entry.get("with") or {}).get("source", "")) == "input":
            yield entry


def _scoped_input_variables(env_data: dict[str, Any]) -> list[tuple[str, str]]:
    """Return every ``(variable id, scope)`` pair the env block requests."""
    return [
        (str(entry.get("id", "?")), str(scope))
        for entry in _input_variables(env_data)
        if (scope := (entry.get("with") or {}).get("scope")) in _VALID_SCOPES
    ]


def _sides_with_a_required_capability(infrastructure: Any) -> set[str]:
    """Return the sides that declare at least one ``required: true`` capability.

    A side is only real when something is required of it. Declaring
    ``sut: {connector: {required: false}}`` describes a capability the run does
    not need, which is not a system anyone can be asked for a value.
    """
    if not isinstance(infrastructure, dict):
        return set()
    return {
        str(side)
        for side, capabilities in infrastructure.items()
        if isinstance(capabilities, dict)
        and any(
            isinstance(requirement, dict) and requirement.get("required") is True
            for requirement in capabilities.values()
        )
    }


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
    return [
        f"Variable '{var_id}' is scoped to '{scope}', but the infrastructure "
        f"block requires no {scope} capability. Declare what the run needs "
        f"(e.g. infrastructure.{scope}.connector.required: true), or remove "
        f"the variable."
        for var_id, scope in scoped
        if scope not in declared_sides
    ]


@dataclass(frozen=True, slots=True)
class FileCollection:
    """An ``env:`` collection whose entries name a file that must exist on disk.

    *key* is both the block under ``env:`` and the directory the file lives in;
    *noun* is how a missing one is named in the error.
    """

    key: str
    noun: str


#: The collections a TCK can reference files from. Both spellings of an entry —
#: a list of ``{id, source}`` and a mapping of ``name: {file}`` — are accepted.
_FILE_COLLECTIONS: tuple[FileCollection, ...] = (
    FileCollection("schemas", "schema"),
    FileCollection("testdata", "testdata"),
)


def _referenced_files(collection: Any, key: str) -> Iterator[tuple[str, str]]:
    """Yield ``(file name, where it was declared)`` for every entry naming a file."""
    if isinstance(collection, list):
        for entry in collection:
            source = entry.get("source") if isinstance(entry, dict) else None
            if source:
                yield str(source), f"env.{key}[{entry.get('id', '?')}]"
    elif isinstance(collection, dict):
        for name, entry in collection.items():
            if isinstance(entry, dict) and "file" in entry:
                yield str(entry["file"]), f"env.{key}.{name}"


def _validate_file_refs(
    manifest_data: dict[str, Any],
    base_dir: Path,
) -> list[str]:
    """Validate that all referenced schema and testdata files exist."""
    env = manifest_data.get("env", {})
    return [
        f"Referenced {collection.noun} file not found: {collection.key}/{file_name} ({declared_at})"
        for collection in _FILE_COLLECTIONS
        for file_name, declared_at in _referenced_files(env.get(collection.key, {}), collection.key)
        if not (base_dir / collection.key / file_name).is_file()
    ]


@dataclass(frozen=True, slots=True)
class BannedStep:
    """A ``uses:`` prefix no script may name, and what the author should write instead.

    *reason* completes the sentence "'<uses>' …", so it reads as one message
    however many prefixes the table grows.
    """

    prefix: str
    reason: str


_BANNED_STEPS: tuple[BannedStep, ...] = (
    BannedStep(
        "precondition/",
        "is no longer accepted (removed by ADR-0021). Migrate to a complex "
        "variable in env.variables with 'uses: config/connector/policy'.",
    ),
    BannedStep(
        "validate/",
        "cannot be used as a standalone step. Place it under the parent step's 'validate:' block.",
    ),
)


def _steps_in(test_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every step of a test file, whichever phase it sits in."""
    for phase in _PHASES:
        steps = test_data.get(phase, [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict):
                yield step


def _reject_banned_steps(
    test_data: dict[str, Any],
    source_label: str,
) -> list[str]:
    """Reject every step whose ``uses`` names a prefix the dialect no longer takes."""
    errors: list[str] = []
    for step in _steps_in(test_data):
        uses = str(step.get("uses", ""))
        for banned in _BANNED_STEPS:
            if uses.startswith(banned.prefix):
                errors.append(
                    f"Rejected step '{step.get('id', '?')}' in {source_label}: "
                    f"'{uses}' {banned.reason}"
                )
    return errors


def _check_test_schema(test_data: dict[str, Any], source_label: str) -> list[str]:
    """Validate a test file against the test JSON schema."""
    return collect_errors(validator_for("tck_test.schema.json"), test_data, source_label)


#: Everything asked of a single test file, in the order an author reads it.
#: A new per-file rule is a row here, not another call site to remember.
_TEST_FILE_RULES: tuple[Callable[[dict[str, Any], str], list[str]], ...] = (
    _check_test_schema,
    _reject_banned_steps,
)

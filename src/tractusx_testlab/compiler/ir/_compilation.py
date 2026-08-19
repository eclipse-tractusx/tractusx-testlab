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

"""Test compilation — builds compiled test dicts with symbol tables and instructions."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from tractusx_testlab.compiler.ir._instructions import (
    build_instructions,
    load_test_file,
    resolve_test_path,
)
from tractusx_testlab.compiler.ir._symbols import build_test_symbols
from tractusx_testlab.models.authoring.definitions import TckTestEntry


def iter_test_entries(manifest_data: dict[str, Any]) -> Iterator[TckTestEntry]:
    """Yield the manifest's ``tests:`` entries, in order, as the model states them.

    A manifest entry is a mapping naming the test file in ``id`` and carrying
    the two things an author may say about it — its ``name`` and whether it is
    ``skippable``. Reading it through :class:`TckTestEntry` is what keeps the
    compiler on the one spelling the schema accepts: entries written any other
    way are rejected here rather than half-understood.
    """
    for entry in manifest_data.get("tests", []):
        yield TckTestEntry.model_validate(entry)


def build_compiled_tests(
    manifest_data: dict[str, Any],
    base_dir: Path,
) -> list[dict[str, Any]]:
    """Build compiled test dicts with symbol tables and instructions."""
    compiled: list[dict[str, Any]] = []

    for entry in iter_test_entries(manifest_data):
        test_path = resolve_test_path(entry.id, base_dir)
        test_data = load_test_file(test_path)
        compiled.append(_compile_single_test(test_data))

    return compiled


def _compile_single_test(
    test_data: dict[str, Any],
) -> dict[str, Any]:
    """Compile a single test into its IR representation."""
    metadata = test_data.get("metadata", {})
    if not metadata:
        metadata = {
            "name": test_data.get("name", ""),
            "version": test_data.get("version", "1.0"),
            "description": test_data.get("description", ""),
        }

    instructions, step_symbols = build_instructions(test_data)
    symbol_table = build_test_symbols(step_symbols)

    compiled: dict[str, Any] = {
        "id": test_data.get("id", ""),
        "metadata": metadata,
        "symbol_table": symbol_table,
        "instructions": instructions,
    }

    # What the test requires of the deployment, and which ecosystem release it
    # certifies against, are part of the test — not decoration on the YAML. The
    # compiled form dropped both, so a run driven from it would demand no
    # capabilities and default to the wrong connector dialect.
    #
    # ``namespace`` is deliberately not carried: it is required to equal the TCK
    # id, which the manifest already states, so it is derivable rather than lost.
    for declared in ("dataspace", "infrastructure"):
        if test_data.get(declared) is not None:
            compiled[declared] = test_data[declared]

    return compiled

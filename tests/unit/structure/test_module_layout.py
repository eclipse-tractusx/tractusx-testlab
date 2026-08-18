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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""A file explains itself from its name, and nothing grows past what it should.

These rules were written down in AGENTS.md with the shell commands to check
them, and nothing ran the commands. Thirteen files were over the limit and five
folders over the count, which is what a written rule nobody checks turns into —
it trains people to ignore the written rules.

Each rule carries an explicit list of the exceptions that exist today. The list
is the debt, visible and countable, and it may only shrink: adding to it fails
review, and removing an entry is how a split proves it happened.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import tractusx_testlab

SRC = Path(tractusx_testlab.__file__).parent

MAX_LINES = 300

#: Files that exceed MAX_LINES today. Each is a split waiting to happen; the
#: number is what it is now, so a file may not grow while it waits.
OVERSIZED: dict[str, int] = {
    "steps/digital_twin_registry/consumer.py": 412,
    "steps/digital_twin/submodel.py": 386,
    "steps/assertions/operators.py": 382,
    "steps/digital_twin/provider/shell.py": 363,
    "steps/step_contract.py": 363,
    "compiler/validation/validator.py": 360,
    "player/execution/player.py": 358,
    "compiler/ir/builder.py": 344,
    "steps/connector/pull_data.py": 342,
    "compiler/validation/_manifest_validation.py": 337,
    "steps/_checks/extraction.py": 330,
    "infrastructure/profiles.py": 329,
    "scripting/step_docs.py": 314,
    "cli/_tck_packager.py": 305,
}

#: Words that name a layer rather than a thing. A module called `utils` tells a
#: reader nothing, and is where code goes when nobody decided where it belongs.
BANNED_NAMES = frozenset(
    {
        "utils",
        "helpers",
        "base",
        "common",
        "core",
        "misc",
        "manager",
        "factory",
        "contracts",
        "checks",
        "rules",
    }
)

#: Modules still carrying one of those names.
BANNED_TODAY: frozenset[str] = frozenset()

#: Basenames used by more than one module. A traceback saying `in manager.py`
#: does not say which subsystem broke.
DUPLICATE_TODAY = frozenset(
    {
        "callbacks.py",
        "compile.py",
        "infrastructure.py",
        "jobs.py",
        "keys.py",
        "loader.py",
        "schema.py",
        # Accepted, not debt: `notification/consumer.py` and
        # `digital_twin_registry/consumer.py` each mirror the step id they
        # implement, which is the rule a reader actually uses to find code. Where
        # the two rules disagree, mirroring the id wins and the directory
        # disambiguates.
        "consumer.py",
    }
)


def _modules() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


class TestFileSize:
    def test_no_new_file_exceeds_the_limit(self) -> None:
        over = {
            _rel(p): len(p.read_text(encoding="utf-8").splitlines())
            for p in _modules()
            if len(p.read_text(encoding="utf-8").splitlines()) > MAX_LINES
        }
        new = sorted(set(over) - set(OVERSIZED))
        assert not new, (
            f"{new} exceed {MAX_LINES} lines and are not in the known list. "
            f"Split along a responsibility seam, or add it with a reason."
        )

    def test_the_known_oversized_files_are_not_growing(self) -> None:
        grown = {
            name: (length, OVERSIZED[name])
            for name, length in (
                (_rel(p), len(p.read_text(encoding="utf-8").splitlines())) for p in _modules()
            )
            if name in OVERSIZED and length > OVERSIZED[name]
        }
        assert not grown, (
            f"Files already over the limit grew: {grown} (now, was). They are "
            f"waiting to be split, not waiting to get bigger."
        )

    def test_a_file_that_was_split_is_removed_from_the_list(self) -> None:
        """The list is the debt. Shrinking a file and leaving it listed hides that."""
        actual = {_rel(p): len(p.read_text(encoding="utf-8").splitlines()) for p in _modules()}
        stale = sorted(
            name for name in OVERSIZED if name not in actual or actual[name] <= MAX_LINES
        )
        assert not stale, f"No longer oversized — remove from OVERSIZED: {stale}"


class TestNaming:
    def test_no_new_module_is_named_for_a_layer(self) -> None:
        offenders = {_rel(p) for p in _modules() if p.stem.lstrip("_") in BANNED_NAMES}
        assert not offenders - BANNED_TODAY, (
            f"{sorted(offenders - BANNED_TODAY)} name a layer, not a thing. "
            f"Name the module for what it defines."
        )

    def test_a_renamed_module_is_removed_from_the_list(self) -> None:
        offenders = {_rel(p) for p in _modules() if p.stem.lstrip("_") in BANNED_NAMES}
        assert not BANNED_TODAY - offenders, (
            f"Renamed — remove from BANNED_TODAY: {sorted(BANNED_TODAY - offenders)}"
        )

    def test_no_new_duplicate_basename(self) -> None:
        counts = Counter(p.name for p in _modules() if p.name != "__init__.py")
        duplicates = {name for name, n in counts.items() if n > 1}
        assert not duplicates - DUPLICATE_TODAY, (
            f"{sorted(duplicates - DUPLICATE_TODAY)} is used by more than one "
            f"module. A traceback naming the file should name the subsystem."
        )

    def test_a_resolved_duplicate_is_removed_from_the_list(self) -> None:
        counts = Counter(p.name for p in _modules() if p.name != "__init__.py")
        duplicates = {name for name, n in counts.items() if n > 1}
        assert not DUPLICATE_TODAY - duplicates, (
            f"No longer duplicated — remove from DUPLICATE_TODAY: "
            f"{sorted(DUPLICATE_TODAY - duplicates)}"
        )

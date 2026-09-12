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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Every cross-step reference in a shipped test must name a published name.

A step's outputs are readable two different ways, and the difference between
them is not visible in the YAML. Inside the step's own ``validate:`` block,
``input:`` reads the output object directly, so a universal slot such as
``body`` resolves whether or not the step declared it. From a *later* step,
``${{ execution.<id>.<field> }}`` reads a context variable, and
:func:`tractusx_testlab.player.execution._step_outputs.store_step_outputs`
writes one variable per key in that step's ``returns:`` block — and nothing at
all when the block is absent.

So a test can read ``body`` on a step in one place and fail to read it on the
same step in another. The compiler does not currently separate the two cases:
it checks that the name is one the step could publish, not that this step said
it would. The result compiles, and then fails at run time with an unresolved
reference — in a job that needs a Kubernetes cluster to reach.

This is the check that closes that gap for everything this repository ships.
It is deliberately written against the YAML rather than against the compiled
IR, because what it is protecting is the thing an author writes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

#: ``${{ <phase>.<step id>.<name> }}`` — the only reference form that reads a
#: value another step published. ``env.``, ``infrastructure.`` and
#: ``metadata.`` references are seeded before the run and are not affected.
_REFERENCE = re.compile(
    r"\$\{\{\s*(setup|execution|teardown)\.([a-z][a-z0-9_]*)\.([a-zA-Z0-9_.\[\]='-]+?)\s*\}\}"
)

_PHASES = ("setup", "execution", "teardown")

_TEST_DIRECTORIES = (
    Path("tests/e2e/connector-dtr-smoke/tests"),
    Path("docs/examples/certificate-management-v2/raw/tests"),
    Path("docs/examples/industry-core-part-type-v2.1.1/tests"),
)


def _shipped_tests() -> list[Path]:
    return sorted(
        path
        for directory in _TEST_DIRECTORIES
        if directory.is_dir()
        for path in directory.glob("*.yaml")
    )


def _unresolvable_references(test: Path) -> list[str]:
    """Return every reference in *test* that names something no step publishes."""
    text = test.read_text(encoding="utf-8")
    document = yaml.safe_load(text) or {}

    published: dict[tuple[str, str], set[str]] = {
        (phase, step.get("id")): set((step.get("returns") or {}).keys())
        for phase in _PHASES
        for step in document.get(phase) or []
    }

    problems: list[str] = []
    for phase, step_id, name in _REFERENCE.findall(text):
        reference = f"{phase}.{step_id}.{name}"
        names = published.get((phase, step_id))
        if names is None:
            problems.append(f"{reference} — no step '{step_id}' in the '{phase}' phase")
            continue
        # A dotted reference reads one context variable whose name is the whole
        # dotted string, so only its first segment can be a declared return.
        root = name.split(".", 1)[0]
        if root not in names:
            declared = ", ".join(sorted(names)) or "nothing"
            problems.append(f"{reference} — step '{step_id}' declares {declared}")
    return problems


def test_the_repository_ships_tests_to_check() -> None:
    """Guards the guard: a glob that stopped matching would pass silently."""
    tests = _shipped_tests()
    assert len(tests) >= 13, [str(path) for path in tests]


@pytest.mark.parametrize("test", _shipped_tests(), ids=lambda path: path.name)
def test_every_cross_step_reference_names_a_declared_return(test: Path) -> None:
    """A reference the runtime cannot resolve is a failure this catches at rest.

    The failure it replaces is the worst kind a TCK has: the package compiles,
    the operator runs it against a real deployment, and one step reports an
    unresolved reference that names a value the author can see written in the
    file two steps above.
    """
    problems = _unresolvable_references(test)
    assert not problems, "\n".join(problems)


def test_the_check_would_notice_an_undeclared_return(tmp_path: Path) -> None:
    """The check has to fail on the shape it exists for, or it proves nothing.

    Written as a test rather than as a fixture because the thing under test is
    the reading of a test: a check that only ever saw correct files would go
    on passing after it stopped looking at anything.
    """
    test = tmp_path / "undeclared.yaml"
    test.write_text(
        yaml.safe_dump(
            {
                "kind": "test",
                "execution": [
                    {"id": "first", "uses": "util/generate_uuid"},
                    {
                        "id": "second",
                        "uses": "util/log",
                        "with": {"value": "${{ execution.first.value }}"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    problems = _unresolvable_references(test)
    assert problems == ["execution.first.value — step 'first' declares nothing"]

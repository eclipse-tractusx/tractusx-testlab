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

"""Topological sort for test scripts respecting depends_on declarations."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tractusx_testlab.scripting.script import TestScript


def topological_sort(scripts: list[TestScript]) -> list[TestScript]:
    """Sort scripts respecting *depends_on* declarations (Kahn's algorithm).

    Scripts without dependencies retain their original relative order.
    Raises ``ValueError`` if a cycle is detected.
    """
    by_name, in_degree, dependents = _build_dependency_graph(scripts)

    queue: deque[str] = deque()
    for script in scripts:
        if in_degree[script.name] == 0:
            queue.append(script.name)

    ordered: list[TestScript] = []
    while queue:
        name = queue.popleft()
        ordered.append(by_name[name])
        for dep_name in dependents[name]:
            in_degree[dep_name] -= 1
            if in_degree[dep_name] == 0:
                queue.append(dep_name)

    if len(ordered) != len(scripts):
        _raise_cycle_error(scripts, ordered)

    return ordered


def _build_dependency_graph(
    scripts: list[TestScript],
) -> tuple[dict[str, TestScript], dict[str, int], dict[str, list[str]]]:
    """Build name lookup, in-degree counts, and dependents adjacency list."""
    by_name: dict[str, TestScript] = {}
    in_degree: dict[str, int] = defaultdict(int)
    dependents: dict[str, list[str]] = defaultdict(list)

    for script in scripts:
        by_name[script.name] = script
        if script.name not in in_degree:
            in_degree[script.name] = 0

    for script in scripts:
        for dep in script.depends_on:
            if dep not in by_name:
                raise ValueError(
                    f"Test '{script.name}' depends on unknown test '{dep}'"
                )
            in_degree[script.name] += 1
            dependents[dep].append(script.name)

    return by_name, in_degree, dependents


def _raise_cycle_error(
    scripts: list[TestScript], ordered: list[TestScript],
) -> None:
    """Raise a descriptive error when a dependency cycle is detected."""
    sorted_names = {script.name for script in ordered}
    cycle_names = [script.name for script in scripts if script.name not in sorted_names]
    raise ValueError(
        f"Dependency cycle detected among tests: {', '.join(cycle_names)}"
    )

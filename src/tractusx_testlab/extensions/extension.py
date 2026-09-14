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

"""What an extension is: a name, what it contributes, and what it checks."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from tractusx_testlab.models.authoring.definitions import TckDefinition, TestDefinition


@dataclass(frozen=True, slots=True)
class ExtensionFinding:
    """One problem an extension found in a test, located the way the compiler reports."""

    message: str
    step_index: int
    field: str
    phase: str


#: An extension's own compile-time check, run only for a TCK that enabled it.
ExtensionCheck = Callable[["TckDefinition", "TestDefinition"], list[ExtensionFinding]]


@dataclass(frozen=True, slots=True)
class Extension:
    """An experimental addition to the syntax or the step catalogue.

    ``step_keys`` and ``validation_keys`` name the keys it adds to a step and to
    a ``validate:`` entry. The keys themselves are declared as fields in
    :mod:`tractusx_testlab.extensions.step_keys`; naming them here is what lets
    the compiler refuse them in a TCK that did not enable the extension.
    ``step_prefix`` reserves a namespace of step ids, e.g. ``labs/``.
    """

    name: str
    summary: str
    step_keys: frozenset[str] = frozenset()
    validation_keys: frozenset[str] = frozenset()
    step_prefix: str | None = None
    check: ExtensionCheck | None = None
    #: Every extension is experimental. The field exists so a report can print
    #: it, and so the day one is not is a visible change rather than a new rule.
    stability: Literal["experimental"] = "experimental"
    #: Where the extension is documented, relative to docs/.
    docs: str = ""


#: The ``with:`` keys under which a flow step carries nested step definitions.
#: A key inside a branch is as much in use as one at the top level.
_NESTED_STEP_KEYS = ("then", "else", "steps")


def written_steps(test: TestDefinition) -> Iterator[tuple[str, int, dict[str, Any]]]:
    """Every step in *test* as the author wrote it, nested flow steps included.

    Yields ``(phase, top-level step index, step)``. A nested step reports under
    the index of the flow step that holds it, because that is the step the
    compiler can point at.
    """
    for phase, steps in (
        ("setup", test.setup),
        ("execution", test.execution),
        ("teardown", test.teardown),
    ):
        for idx, step in enumerate(steps):
            for written in _with_nested(step.model_dump(by_alias=True, exclude_none=True)):
                yield phase, idx, written


def _with_nested(step: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield step
    if not str(step.get("uses", "")).startswith("flow/"):
        return
    params = step.get("with") or {}
    for key in _NESTED_STEP_KEYS:
        for nested in params.get(key) or []:
            if isinstance(nested, dict):
                yield from _with_nested(nested)

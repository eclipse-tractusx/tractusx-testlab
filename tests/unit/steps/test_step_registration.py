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

"""The step inventory on disk and the step registry at runtime are the same set.

A step registered any way other than by ``@step("…")`` on its class, or declared
in a module nothing imports, is a step that resolves in one process and raises
"No implementation found for step type" in the next.  These tests read the
source with ``ast`` — not by importing it — so the decorators on disk are
compared against what importing actually registered.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import tractusx_testlab.steps
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps.step_contract import BaseStep

_STEPS_DIR = Path(tractusx_testlab.steps.__file__).parent

#: Step classes that are deliberately not registered: shared bases that exist
#: only for the registered subclasses below them to inherit ``execute`` from.
_ABSTRACT_STEP_CLASSES = {"OAuth2GetTokenStep"}

_STEP_DECORATOR = re.compile(r"^step\((['\"])(?P<step_type>.+?)\1")


def _decorated_step_types() -> dict[str, str]:
    """Every ``@step("…")`` under the steps package, mapped to ``file:line``."""
    found: dict[str, str] = {}
    for path in sorted(_STEPS_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for decorator in node.decorator_list:
                match = _STEP_DECORATOR.match(ast.unparse(decorator))
                if match:
                    where = f"{path.relative_to(_STEPS_DIR)}:{node.lineno}"
                    found[match.group("step_type")] = where
    return found


def _step_class_names() -> dict[str, str]:
    """Every class deriving from ``BaseStep`` on disk, mapped to ``file:line``."""
    classes: dict[str, tuple[str, list[str]]] = {}
    for path in sorted(_STEPS_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [
                re.sub(r"\[.*\]", "", ast.unparse(base)).split(".")[-1]
                for base in node.bases
            ]
            classes[node.name] = (f"{path.relative_to(_STEPS_DIR)}:{node.lineno}", bases)

    def derives_from_base_step(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name in seen or name not in classes:
            return False
        return any(
            base == BaseStep.__name__
            or derives_from_base_step(base, seen | {name})
            for base in classes[name][1]
        )

    return {
        name: where
        for name, (where, _) in classes.items()
        if derives_from_base_step(name)
    }


def _decorated_class_names() -> set[str]:
    """Names of the classes that carry a ``@step("…")`` decorator."""
    names: set[str] = set()
    for path in sorted(_STEPS_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                _STEP_DECORATOR.match(ast.unparse(d)) for d in node.decorator_list
            ):
                names.add(node.name)
    return names


class TestStepRegistration:
    def test_every_decorated_step_is_registered(self):
        """A decorator in a module nothing imports registers nothing."""
        decorated = _decorated_step_types()
        registered = set(StepRegistry.list_step_types())
        unreachable = {
            step_type: where
            for step_type, where in decorated.items()
            if step_type not in registered
        }
        assert not unreachable, (
            "declared with @step but never registered — the module is not imported "
            f"by its package __init__: {unreachable}"
        )

    def test_every_registered_step_comes_from_a_decorator(self):
        """No step is registered by an imperative ``step(...)(Cls)`` call.

        Such a registration is invisible to a decorator search of the tree and
        binds the step's availability to one package ``__init__`` being imported.
        """
        undeclared = set(StepRegistry.list_step_types()) - set(_decorated_step_types())
        assert not undeclared, (
            "registered without a @step decorator on the class: "
            f"{sorted(undeclared)}"
        )

    def test_every_step_class_carries_a_decorator(self):
        """Every ``BaseStep`` subclass is either registered or a declared base."""
        undecorated = {
            name: where
            for name, where in _step_class_names().items()
            if name not in _decorated_class_names()
            and name not in _ABSTRACT_STEP_CLASSES
        }
        assert not undecorated, (
            "BaseStep subclass with no @step decorator — register it, or add it to "
            f"_ABSTRACT_STEP_CLASSES if it is only a shared base: {undecorated}"
        )


class TestAStepsPathMirrorsItsId:
    """``<category>/<...>`` in a TCK locates the module without a grep.

    This is the rule a reader actually uses. Before it was enforced, 26 of the
    54 steps lived somewhere their id did not suggest: ``http/http_request`` in
    ``connector/utils.py``, every ``mock/*`` step under ``server/``, and both
    twin-registry namespaces in one 1,063-line ``industry/dtr.py``.
    """

    def test_every_step_lives_under_its_category(self) -> None:
        misplaced = {
            step_type: location
            for step_type, location in _decorated_step_types().items()
            if not location.split(":")[0].startswith(
                step_type.split("/")[0].replace("-", "_") + "/"
            )
        }
        assert not misplaced, (
            f"These steps are not under the directory their id names: {misplaced}. "
            f"A step id's first segment is its package, with '-' written as '_'."
        )


class TestEveryRegisteredStepIsReachable:
    """A step in the catalog is one a TCK may actually use.

    ``validate/assert``, ``validate/field`` and ``validate/schema`` were
    registered, documented in the step reference, and rejected by the compiler
    as steps — 236 lines an author could find and could not call.
    """

    def test_no_registered_step_is_rejected_by_the_validator(self) -> None:
        from tractusx_testlab.compiler.validation._manifest_validation import (
            _reject_banned_steps,
        )

        rejected = [
            step_type
            for step_type in StepRegistry.list_step_types()
            if _reject_banned_steps(
                {"execution": [{"id": "s", "uses": step_type}]}, "probe"
            )
        ]
        assert not rejected, (
            f"The registry advertises {rejected}, which the compiler refuses to "
            f"accept as steps. One of the two is wrong."
        )

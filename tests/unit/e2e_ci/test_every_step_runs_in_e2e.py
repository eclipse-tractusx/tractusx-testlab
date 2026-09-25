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

## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""No step ships without the E2E suite running it against a real dataspace.

``tests/e2e/README.md`` promises that the connector-dtr-smoke TCK uses every
step in the catalogue. The workflow that runs it cannot notice a step that no
test names, so a new step used to land with its unit tests and nothing live.
This reads the TCK's tests and fails on the first registered step none of them
uses, which is the moment to add it there.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from tests.paths import TESTS_DIR
from tractusx_testlab.authoring.registry import StepRegistry

_E2E_TESTS = TESTS_DIR / "e2e" / "connector-dtr-smoke" / "tests"


def _uses(node: Any) -> set[str]:
    """Every ``uses:`` in a test, nested flow steps and checks included."""
    if isinstance(node, dict):
        found = {node["uses"]} if isinstance(node.get("uses"), str) else set()
        return found.union(*(_uses(value) for value in node.values()))
    if isinstance(node, list):
        return set().union(*(_uses(item) for item in node))
    return set()


_USED = set().union(
    *(_uses(yaml.safe_load(path.read_text(encoding="utf-8"))) for path in _E2E_TESTS.glob("*.yaml"))
)


@pytest.mark.parametrize("step_type", sorted(StepRegistry.list_step_types()))
def test_the_e2e_suite_runs_the_step(step_type: str) -> None:
    assert step_type in _USED, (
        f"'{step_type}' is in the catalogue but no test in {_E2E_TESTS.relative_to(TESTS_DIR)} "
        "uses it; add it to the E2E suite (tests/e2e/README.md)"
    )


def test_the_e2e_suite_was_read() -> None:
    assert _USED, f"no step found under {_E2E_TESTS}"

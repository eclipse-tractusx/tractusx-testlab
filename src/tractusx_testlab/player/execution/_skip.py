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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Skip resolution — validates the operator's ``skip_tests`` and ``only_tests`` against the TCK.

Extracted from ``player.py`` to keep each module under 300 lines and to isolate
the pure skip-validation logic from the execution coordinator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models.primitives.exceptions import (
    SkipNotAllowedError,
    UnknownFocusTestError,
)
from tractusx_testlab.player.execution._plan import TestPlan

if TYPE_CHECKING:
    from tractusx_testlab.authoring.test import Tck


def requested_ids(runtime_vars: dict | None, key: str) -> list[str]:
    """The test ids the runtime variable *key* names (``skip_tests``, ``only_tests``).

    A string arrives from ``--var skip_tests=a,b``, where the shell cannot
    express a list. A comma is not legal in a test id, so splitting on it is
    unambiguous — and without it the whole string reads as one unknown id.
    """
    raw = (runtime_vars or {}).get(key) or []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [str(entry) for entry in raw]


def resolve_skip_ids(tck: Tck, runtime_vars: dict | None) -> frozenset[str]:
    """Return the resolved set of test IDs to skip, validating each is allowed.

    Reads the ``skip_tests`` key from *runtime_vars* and cross-references it
    against the TCK's test entries.  Raises :class:`SkipNotAllowedError` before
    any test executes when:

    * A requested ID does not exist in the TCK's test list.
    * A requested ID exists but the entry is not marked ``skippable: true``.

    Args:
        tck: The loaded TCK to validate against.
        runtime_vars: Optional runtime variable dict that may contain ``skip_tests``
            (a list of test-file IDs such as ``["test-cert.yaml"]``).

    Returns:
        Frozen set of test IDs the player must skip during this run.

    Raises:
        SkipNotAllowedError: If any requested test ID is unknown or not skippable.
    """
    skip_ids = requested_ids(runtime_vars, "skip_tests")
    if not skip_ids:
        return frozenset()

    all_test_ids = {s.test_id for s in tck.tests}
    skippable_ids = {s.test_id for s in tck.tests if s.skippable}

    unknown = [sid for sid in skip_ids if sid not in all_test_ids]
    if unknown:
        raise SkipNotAllowedError(unknown, reason="not found in TCK tests list")

    not_allowed = [sid for sid in skip_ids if sid not in skippable_ids]
    if not_allowed:
        raise SkipNotAllowedError(not_allowed)

    return frozenset(skip_ids)


def resolve_only_ids(tck: Tck, runtime_vars: dict | None) -> frozenset[str]:
    """Return the tests a focus run (``only_tests``) runs; empty for a plain run.

    Every other test is skipped whatever its ``skippable`` says: a focus run
    is a look at some tests, not a verdict on the TCK.

    Raises:
        UnknownFocusTestError: Before any test runs, if an id names no test of the TCK.
    """
    only_ids = requested_ids(runtime_vars, "only_tests")
    all_test_ids = {test.test_id for test in tck.tests}
    unknown = [tid for tid in only_ids if tid not in all_test_ids]
    if unknown:
        raise UnknownFocusTestError(unknown)
    return frozenset(only_ids)


def resolve_plan(tck: Tck, runtime_vars: dict | None) -> TestPlan:
    """The run's :class:`TestPlan`: ``skip_tests`` and ``only_tests``, both validated.

    Raises:
        SkipNotAllowedError: ``skip_tests`` names an unknown or required test, or
            ``only_tests`` an unknown one (:class:`UnknownFocusTestError`).
    """
    skip_ids, only_ids = resolve_skip_ids(tck, runtime_vars), resolve_only_ids(tck, runtime_vars)
    return TestPlan(tck.tests, skip_ids, only_ids)

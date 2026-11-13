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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Which tests of a run run, and why each one that does not was skipped.

Three things leave a test out: the operator's ``skip_tests``, a focus run's
``only_tests`` (every other test), and a test marked ``on_failure: stop`` that
failed (every later test, in manifest order). The first is skipped without a
reason, as it always was; the other two carry the reason a reader is shown.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import TYPE_CHECKING

from tractusx_testlab.models.primitives.enums import TestStatus

if TYPE_CHECKING:
    from tractusx_testlab.authoring.test import Test
    from tractusx_testlab.models import TestResult

#: The reason a test is skipped because an earlier ``on_failure: stop`` test failed.
STOPPED_REASON = "stopped: {test_id} failed and is marked on_failure: stop"
#: The reason a test is skipped because a focus run did not select it.
NOT_SELECTED_REASON = "not selected for this focus run"

#: Outcomes that do not trip ``on_failure: stop``.
_PASSING: frozenset[TestStatus] = frozenset({TestStatus.COMPLETED, TestStatus.SKIPPED})


class TestPlan:
    """The run's selection (``skip_tests``, ``only_tests``) and whether a test stopped it."""

    __test__ = False  # a run plan, not a pytest test class
    __slots__ = ("_only_ids", "_order", "_skip_ids", "_stopped_by")

    def __init__(
        self, tests: Sequence[Test], skip_ids: Collection[str] = (), only_ids: Collection[str] = ()
    ) -> None:
        self._order = {test.test_id: idx for idx, test in enumerate(tests)}
        self._skip_ids = frozenset(skip_ids)
        self._only_ids = frozenset(only_ids)
        self._stopped_by: str | None = None

    @property
    def only_tests(self) -> list[str]:
        """The tests a focus run runs, in manifest order; empty for a plain run."""
        return [test_id for test_id in self._order if test_id in self._only_ids]

    @property
    def left_out_ids(self) -> frozenset[str]:
        """Every test the run leaves out before it starts: ``skip_tests`` and, focused, the rest."""
        if not self._only_ids:
            return self._skip_ids
        return self._skip_ids | {tid for tid in self._order if tid not in self._only_ids}

    @property
    def stopped_by(self) -> str | None:
        """The ``on_failure: stop`` test whose failure stopped the run, if one did."""
        return self._stopped_by

    def leaves_out(self, test: Test) -> bool:
        """Whether the planned sequence skips *test* rather than running it."""
        return test.test_id in self._skip_ids or self.reason(test) is not None

    def reason(self, test: Test) -> str | None:
        """Why *test* is skipped, or ``None`` (run it, or skipped by ``skip_tests``)."""
        if test.test_id in self._skip_ids:
            return None
        if self._only_ids and test.test_id not in self._only_ids:
            return NOT_SELECTED_REASON
        stopped_by = self._stopped_by
        if stopped_by is not None and self._order[test.test_id] > self._order[stopped_by]:
            return STOPPED_REASON.format(test_id=stopped_by)
        return None

    def record(self, test: Test, result: TestResult) -> TestResult:
        """Note *result* of *test*, return it; a failed ``on_failure: stop`` test stops the run."""
        if self._stopped_by is None and test.on_failure == "stop" and result.status not in _PASSING:
            self._stopped_by = test.test_id
        return result

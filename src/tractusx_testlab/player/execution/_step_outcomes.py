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

"""What became of the running test's steps, for a reference that reads one.

A step that published nothing under its id says nothing about why: it may have
failed, been skipped, or have no ``returns:``. A reference to one of its outputs
is the author's mistake in two of those and follows from the step's failure in
the third (``resolver.origin_of``), so the runners record which it was rather
than leave the resolver to infer it from what is in scope.
"""

from __future__ import annotations

from dataclasses import dataclass

from tractusx_testlab.models import StepStatus
from tractusx_testlab.models.runtime.results import ENGINE_FAULT_PREFIX, StepResult


@dataclass(frozen=True)
class StepOutcome:
    """What became of one step: its status, and whose its failure was if it failed."""

    status: StepStatus
    #: ``errors[].origin`` of the step's failure; ``None`` unless it failed.
    origin: str | None = None


def failure_origin(result: StepResult) -> str:
    """Who a failed step's failure belongs to, as the trace publishes it.

    ``error_origin``, else what a result written before that field existed
    says through ``ENGINE_FAULT_PREFIX``. A failed check is a verdict: ``sut``.
    """
    if result.error_origin:
        return result.error_origin
    return "engine" if (result.error or "").startswith(ENGINE_FAULT_PREFIX) else "sut"


class StepOutcomes:
    """The outcomes of one test's steps, by ``<phase>.<id>``, and what stopped it.

    Held by ``StepContext`` and cleared per test (``step_runner.run_test``): the
    context lives for the whole run, and two tests may give a step the same id.
    """

    __slots__ = ("_outcomes", "_stopped_by")

    def __init__(self) -> None:
        self._outcomes: dict[str, StepOutcome] = {}
        self._stopped_by: str | None = None

    def clear(self) -> None:
        """Forget the test before."""
        self._outcomes.clear()
        self._stopped_by = None

    def record(
        self,
        namespace: str | None,
        step_id: str | None,
        status: StepStatus,
        origin: str | None = None,
    ) -> None:
        """Note that *step_id* in *namespace* passed, failed or was skipped.

        A step without an id, or outside a phase, cannot be referenced and is
        not recorded.
        """
        if namespace and step_id:
            self._outcomes[f"{namespace}.{step_id}"] = StepOutcome(status, origin)

    def record_result(self, namespace: str | None, step_id: str | None, result: StepResult) -> None:
        """:meth:`record` for a step that ran, read off its result."""
        failed = result.status == StepStatus.FAILED
        self.record(namespace, step_id, result.status, failure_origin(result) if failed else None)

    def outcome_of(self, step: str) -> StepOutcome | None:
        """What became of *step* (``<phase>.<id>``); ``None`` when it never ran."""
        return self._outcomes.get(step)

    def record_stop(self, origin: str) -> None:
        """Note who the failure that stopped a phase belongs to — the phase runner does.

        A step that never ran is one this failure kept from running, and a
        reference to its outputs follows from it. Only the first counts: setup
        stopping keeps execution from running at all.
        """
        if self._stopped_by is None:
            self._stopped_by = origin

    @property
    def stopped_by(self) -> str | None:
        """Who the failure that stopped the test belongs to; ``None`` when none did."""
        return self._stopped_by

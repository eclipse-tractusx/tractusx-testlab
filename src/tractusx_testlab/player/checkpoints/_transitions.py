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

"""What a checkpoint becomes when its step, its test or its run ends (ADR-0028).

Pure rules, kept apart from the tracker that applies them, so the state machine
reads in one place:

* its step **completed**: ``cleared`` if it was asked (answered then, if
  nothing answered it before), ``skipped`` if it never had to be (a choice of
  one option, taken without asking);
* its step was **skipped**: ``skipped``;
* its step **failed**: ``failed`` once it was answered, ``timed_out`` for a
  question still open, ``not_reached`` if it was never asked; a step that
  stopped because the run was cancelled leaves an open question
  ``not_reached``, as does a step interrupted without an outcome;
* a checkpoint a flow step carries and never reached follows the flow step:
  ``skipped`` when it completed or was skipped, ``not_reached`` when it failed;
* its **test** ended without reaching it: ``skipped`` when the test passed or
  was skipped, ``not_reached`` when it failed or the run was cancelled; one
  still ``now`` is ``not_reached``;
* the **run** ended: whatever is still ``ahead`` or ``now`` is ``not_reached``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tractusx_testlab.models.primitives.enums import StepStatus, TestStatus
from tractusx_testlab.models.runtime.checkpoints import CheckpointStatus
from tractusx_testlab.player.checkpoints.frames import StepFrame

#: States a run that ended leaves no checkpoint in.
OPEN = frozenset({"ahead", "now"})
#: Test outcomes that ran without failing.
_TEST_PASSED = frozenset({TestStatus.COMPLETED, TestStatus.SKIPPED})


def own_step_ended(
    status: CheckpointStatus,
    frame: StepFrame,
    outcome: StepStatus | None,
    *,
    asks: bool,
    cancelled: bool,
    at: datetime,
) -> dict[str, Any]:
    """The changes to the checkpoint *frame*'s step is, now that the step ended with *outcome*."""
    if outcome is StepStatus.SKIPPED or (outcome is StepStatus.PASSED and not frame.asked):
        return {"state": "skipped"}
    if outcome is StepStatus.PASSED:
        if frame.answered:
            return {"state": "cleared"}
        return {"state": "cleared", "answered_at": at, "response_s": seconds(status.asked_at, at)}
    if not frame.asked:
        return {"state": "not_reached"}
    if frame.answered:
        return {"state": "failed", "response_s": None}
    if cancelled or outcome is None:
        return {"state": "not_reached"}
    return {"state": "timed_out" if asks else "failed", "answered_at": at, "response_s": None}


def carried_step_ended(outcome: StepStatus | None) -> str:
    """The state of a checkpoint a flow step carries and never reached, once the flow step ended."""
    return "skipped" if outcome in (StepStatus.PASSED, StepStatus.SKIPPED) else "not_reached"


def test_ended(state: str, outcome: TestStatus, cancelled: bool = False) -> str | None:
    """The state of a checkpoint whose test ended while it was *state*; ``None`` keeps it.

    A test skipped because the run was cancelled did not choose to skip it.
    """
    if state == "ahead":
        passed = outcome in _TEST_PASSED and not cancelled
        return "skipped" if passed else "not_reached"
    return "not_reached" if state == "now" else None


def seconds(start: datetime | None, end: datetime) -> float | None:
    """Seconds from *start* to *end*, to the millisecond; ``None`` without a start."""
    if start is None:
        return None
    return round(max((end - start).total_seconds(), 0.0), 3)

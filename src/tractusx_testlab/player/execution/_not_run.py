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


"""The result a step leaves behind when it did not run.

Two steps never execute and both still have to appear in the run: the one whose
``if:`` said no, and the one whose ``uses:`` names something the registry does
not have. Neither can report a wire or an output, so what they report is a
status and — for the missing one — why nothing could be run at all. A phase that
silently omitted them would produce a result shorter than the script.
"""

from __future__ import annotations

from tractusx_testlab.models.primitives.enums import StepPhase, StepStatus
from tractusx_testlab.models.runtime.results import StepResult


def skipped_result(step_name: str, step_type: str, phase: StepPhase) -> StepResult:
    """The result of a step whose ``if:`` condition was false."""
    return StepResult(
        step_name=step_name,
        step_type=step_type,
        phase=phase,
        status=StepStatus.SKIPPED,
    )


def missing_step_result(step_name: str, step_type: str, phase: StepPhase) -> StepResult:
    """The result of a step whose ``uses:`` names no registered implementation."""
    return StepResult(
        step_name=step_name,
        step_type=step_type,
        phase=phase,
        status=StepStatus.FAILED,
        error=f"No implementation found for step type '{step_type}'",
    )

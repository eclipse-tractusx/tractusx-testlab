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

"""Teardown phase runner — runs unconditionally, never stops on failure."""

from __future__ import annotations

from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.execution.phases._run_phase import (
    FailurePolicy,
    PhaseConfig,
    _run_phase,
)
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.scripting.script import TestScript

_TEARDOWN_CONFIG = PhaseConfig(
    phase=StepPhase.TEARDOWN,
    phase_label="teardown",
    failure_policy=FailurePolicy.CONTINUE,
    evaluate_conditions=False,
    use_pause_gate=False,
    store_outputs=False,
)


async def run_teardown(
    script: TestScript,
    context: StepContext,
    job_id: str,
    monitor: ExecutionMonitor,
    jobs: JobManager | None = None,
) -> list[StepResult]:
    """Run teardown steps unconditionally (even after failure)."""
    results, _ = await _run_phase(script, context, job_id, monitor, jobs, _TEARDOWN_CONFIG)
    return results

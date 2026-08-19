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

"""Running a TCK's scripts in the order its manifest lists them.

Split out of the player because it answers a question of its own: given a plan
and a set of skips, which scripts run and in what order. The player's job is the
run's lifecycle around that — the job, the transcript, the trace, the teardown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tractusx_testlab.player.execution._trace_formatter import make_intentionally_skipped_result
from tractusx_testlab.player.execution.step_runner import run_script

if TYPE_CHECKING:
    from tractusx_testlab.models.runtime.results import ScriptResult
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.player.execution.monitor import ExecutionMonitor
    from tractusx_testlab.player.jobs import JobManager
    from tractusx_testlab.scripting.script import TestScript


async def run_scripts(
    scripts: list[TestScript],
    context: StepContext,
    job: Any,
    monitor: ExecutionMonitor,
    jobs: JobManager,
    skip_ids: frozenset[str],
) -> list[ScriptResult]:
    """Run each script in manifest order, honouring the operator's skips.

    Scripts run in the order the manifest lists them. There is no inter-script
    dependency declaration in v1-alpha — a script says what it needs through the
    infrastructure it requires and the variables it reads, not by naming another
    script.
    """
    script_results: list[ScriptResult] = []

    for idx, script in enumerate(scripts):
        if script.test_id in skip_ids:
            skipped = make_intentionally_skipped_result(script)
            script_results.append(skipped)
            monitor.on_script_started(job.job_id, script.definition.id, idx)
            monitor.on_script_completed(job.job_id, skipped)
            continue

        monitor.on_script_started(job.job_id, script.definition.id, idx)
        job.current_script = script.name

        script_result = await run_script(script, context, job.job_id, monitor, jobs)
        script_results.append(script_result)
        monitor.on_script_completed(job.job_id, script_result)

    return script_results

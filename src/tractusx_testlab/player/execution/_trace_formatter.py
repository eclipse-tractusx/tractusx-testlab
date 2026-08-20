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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Trace formatting — builds result objects from execution data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging.structured import StructuredLogger
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models import (
    AssertionSummary,
    ScriptResult,
    ScriptStatus,
    TckResult,
)
from tractusx_testlab.player.execution.monitor import ExecutionMonitor
from tractusx_testlab.player.jobs import JobManager
from tractusx_testlab.scripting.script import TestScript

_NON_FAILING_STATUSES: frozenset[ScriptStatus] = frozenset(
    {
        ScriptStatus.COMPLETED,
        ScriptStatus.SKIPPED,
    }
)


def make_intentionally_skipped_result(script: TestScript) -> ScriptResult:
    """Build a SKIPPED result for a test intentionally omitted by the operator.

    this result uses ``ScriptStatus.SKIPPED`` so the overall TCK result remains
    ``COMPLETED`` when all non-skipped tests pass.
    """
    now = datetime.now(UTC)
    return ScriptResult(
        script_name=script.name,
        dataspace_version=script.dataspace_version,
        status=ScriptStatus.SKIPPED,
        execution=[],
        started_at=now,
        finished_at=now,
        total_duration_s=0.0,
        assertion_summary=AssertionSummary(total=0, passed=0, failed_hard=0, failed_soft=0),
    )


def build_tck_result(
    tck_name: str,
    script_results: list[ScriptResult],
    started_at: datetime,
    finished_at: datetime,
) -> TckResult:
    """Aggregate script results into a single TckResult.

    The overall status is ``COMPLETED`` when every script is either ``COMPLETED``
    or ``SKIPPED`` (intentionally omitted by the operator).  Any ``FAILED`` or
    ``CANCELLED`` script makes the overall result ``FAILED``.
    """
    all_ok = all(script.status in _NON_FAILING_STATUSES for script in script_results)
    return TckResult(
        tck_id=tck_name,
        status=ScriptStatus.COMPLETED if all_ok else ScriptStatus.FAILED,
        scripts=script_results,
        started_at=started_at,
        finished_at=finished_at,
    )


def open_run_records(
    logger: StructuredLogger,
    config: TestlabConfig,
    tck_id: str,
    job_id: str,
) -> tuple[StructuredLogger, ExecutionTrace]:
    """Open the two records a run leaves behind: the transcript and the trace.

    They are opened together because they are closed together and because the
    split between them — text for a person under ``logs_dir``, CloudEvents for a
    tool under ``data_dir`` (ADR-0016) — is one decision, made here rather than
    re-derived wherever a run happens to start.
    """
    job_logger = logger.for_job(job_id)
    trace = ExecutionTrace.for_job(tck_id, job_id, config.data_dir)
    if trace.path is not None:
        job_logger.info("tck.trace.opened", trace=str(trace.path))
    return job_logger, trace


def finalize_job(
    jobs: JobManager,
    job: Any,
    result: TckResult,
    monitor: ExecutionMonitor,
    job_logger: StructuredLogger,
    trace: ExecutionTrace | None = None,
) -> None:
    """Update job status and close both records after execution completes."""
    job.result = result
    # `status`, not a step tally: the verdict is the aggregate the TCK reports.
    if result.status in _NON_FAILING_STATUSES:
        jobs.complete(job.job_id)
        monitor.on_job_completed(job.job_id)
    else:
        reason = "One or more scripts failed"
        jobs.fail(job.job_id, reason)
        monitor.on_job_failed(job.job_id, error=reason)
    # After the verdict is published: ``tck.end`` is a trace event too.
    if trace is not None:
        trace.close()
    job_logger.close()

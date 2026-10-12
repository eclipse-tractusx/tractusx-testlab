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

"""Setting a run up to follow its checkpoints, and publishing its plan."""

from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING

from tractusx_testlab.authoring._checkpoints import collect_checkpoints
from tractusx_testlab.player.checkpoints.tracker import CheckpointTracker

if TYPE_CHECKING:
    from tractusx_testlab.authoring.test import Tck
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.player.execution.monitor import ExecutionMonitor
    from tractusx_testlab.player.jobs import JobManager


def follow_checkpoints(
    context: StepContext,
    monitor: ExecutionMonitor,
    jobs: JobManager,
    tck: Tck,
    skip_tests: Collection[str],
) -> CheckpointTracker:
    """Follow the checkpoints of *tck*'s run, less *skip_tests*, and publish them ``ahead``.

    The tracker is bound to the run's context, where the runner opens a frame
    for every step, and to its monitor, which tells it what happens and
    publishes what changes. Called once, before the first test.
    """
    job_id = str(context.job.job_id)
    tracker = CheckpointTracker(
        collect_checkpoints(tck, skip_tests),
        monitor.checkpoint_publisher(job_id),
        lambda: jobs.is_cancelled(job_id),
    )
    context.bind_checkpoints(tracker)
    monitor.follow_checkpoints(tracker)
    tracker.plan()
    return tracker

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The fields every execution event shares — the base of ``events`` and ``hold_events``."""

from __future__ import annotations

from pydantic import BaseModel

from tractusx_testlab.models.runtime.checkpoints import CheckpointRef


class _ExecutionEvent(BaseModel):
    """Fields shared by every execution event."""

    job_id: str


class _StepEvent(_ExecutionEvent):
    """Fields shared by every event about one step.

    ``attempt`` says which run of the step this is within the job, from 1: a
    step a ``flow/retry`` runs again, or whose test is run again, says so, and
    two runs of one step never publish the same event (ADR-0016). ``checkpoint``
    names the checkpoint the step is, and which attempt of it, when it is one
    (ADR-0027): every exchange at a checkpoint can be found by it.
    """

    test_id: str
    step_id: str | None = None
    attempt: int = 1
    checkpoint: CheckpointRef | None = None

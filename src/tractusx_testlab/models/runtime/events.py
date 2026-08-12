#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude, Model: Claude Sonnet 5).
## It was reviewed and tested by a human committer.

"""Execution event models — typed payloads published by the ExecutionMonitor.

Every event carries an explicit ``kind`` discriminator (see
:class:`~tractusx_testlab.models.primitives.enums.EventKind`) so a consumer
never needs to sniff ``step_type`` or other free-text fields to decide what
happened. Payloads reuse the existing result models (``StepResult``,
``ScriptResult``, ``AssertionResult``) rather than duplicating their fields.

See ``docs/developer/execution-events.md`` for the full wire contract.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel

from tractusx_testlab.models.primitives.enums import EventKind, JobStatus
from tractusx_testlab.models.runtime.results import AssertionResult, ScriptResult, StepResult


class _ExecutionEvent(BaseModel):
    """Fields shared by every execution event."""

    job_id: str


class JobStartedEvent(_ExecutionEvent):
    """A job began executing."""

    kind: Literal[EventKind.JOB_STARTED] = EventKind.JOB_STARTED
    tck_id: str


class JobPausedEvent(_ExecutionEvent):
    """A running job was paused by the operator."""

    kind: Literal[EventKind.JOB_PAUSED] = EventKind.JOB_PAUSED


class JobResumedEvent(_ExecutionEvent):
    """A paused (or waiting) job resumed execution."""

    kind: Literal[EventKind.JOB_RESUMED] = EventKind.JOB_RESUMED


class JobCompletedEvent(_ExecutionEvent):
    """A job finished with every script completed or intentionally skipped."""

    kind: Literal[EventKind.JOB_COMPLETED] = EventKind.JOB_COMPLETED
    status: Literal[JobStatus.COMPLETED] = JobStatus.COMPLETED


class JobFailedEvent(_ExecutionEvent):
    """A job finished with at least one script failure, or raised an exception."""

    kind: Literal[EventKind.JOB_FAILED] = EventKind.JOB_FAILED
    status: Literal[JobStatus.FAILED] = JobStatus.FAILED
    error: Optional[str] = None


class JobCancelledEvent(_ExecutionEvent):
    """The operator cancelled the job before it reached a terminal state."""

    kind: Literal[EventKind.JOB_CANCELLED] = EventKind.JOB_CANCELLED
    status: Literal[JobStatus.CANCELLED] = JobStatus.CANCELLED


class ScriptStartedEvent(_ExecutionEvent):
    """A script within the job began executing."""

    kind: Literal[EventKind.SCRIPT_STARTED] = EventKind.SCRIPT_STARTED
    script: str
    index: int


class ScriptCompletedEvent(_ExecutionEvent):
    """A script finished; ``result.status`` carries the outcome."""

    kind: Literal[EventKind.SCRIPT_COMPLETED] = EventKind.SCRIPT_COMPLETED
    result: ScriptResult


class StepStartedEvent(_ExecutionEvent):
    """A step began executing."""

    kind: Literal[EventKind.STEP_STARTED] = EventKind.STEP_STARTED
    script: str
    step_id: Optional[str] = None
    step_index: int
    step_type: str
    step_name: str
    phase: str


class StepCompletedEvent(_ExecutionEvent):
    """A step finished with ``StepStatus.PASSED``."""

    kind: Literal[EventKind.STEP_COMPLETED] = EventKind.STEP_COMPLETED
    script: str
    step_id: Optional[str] = None
    result: StepResult


class StepFailedEvent(_ExecutionEvent):
    """A step finished with ``StepStatus.FAILED`` — a hard assertion or an exception."""

    kind: Literal[EventKind.STEP_FAILED] = EventKind.STEP_FAILED
    script: str
    step_id: Optional[str] = None
    result: StepResult


class StepSkippedEvent(_ExecutionEvent):
    """A step was skipped — its ``if:`` condition was false, or no implementation exists."""

    kind: Literal[EventKind.STEP_SKIPPED] = EventKind.STEP_SKIPPED
    script: str
    step_id: Optional[str] = None
    result: StepResult


class StepWaitingEvent(_ExecutionEvent):
    """A step is blocked waiting for an external callback to arrive."""

    kind: Literal[EventKind.STEP_WAITING] = EventKind.STEP_WAITING
    step_index: int
    listener_url: str


class AssertionResultEvent(_ExecutionEvent):
    """One assertion was evaluated against a step's output.

    Emitted for every assertion in a step's ``validate:`` block, ahead of the
    step's own ``step_completed`` / ``step_failed`` / ``step_skipped`` event,
    so a consumer can track individual assertion outcomes without inferring
    them from the step's ``step_type``.
    """

    kind: Literal[EventKind.ASSERTION_RESULT] = EventKind.ASSERTION_RESULT
    script: str
    step_id: Optional[str] = None
    step_name: str
    assertion: AssertionResult


ExecutionEvent = Union[
    JobStartedEvent,
    JobPausedEvent,
    JobResumedEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobCancelledEvent,
    ScriptStartedEvent,
    ScriptCompletedEvent,
    StepStartedEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepSkippedEvent,
    StepWaitingEvent,
    AssertionResultEvent,
]

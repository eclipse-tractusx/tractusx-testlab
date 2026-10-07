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

"""The events of a paused run on hold (``player.execution.hold``).

Kept beside ``events`` rather than in it only for its length; ``events``
re-exports them, and ``ExecutionEvent`` includes them.
"""

from __future__ import annotations

from typing import Literal

from tractusx_testlab.models.primitives.enums import EventKind
from tractusx_testlab.models.runtime._event_base import _ExecutionEvent
from tractusx_testlab.models.runtime.listener import Listener


class JobHeldEvent(_ExecutionEvent):
    """A paused job has stopped and withdrawn what it offered (``player.execution.hold``).

    ``withdrawn`` are the contract definitions the run created and has now
    deleted, in the order they were created; ``kept`` the ones the connector
    would not delete, with why. The run's mocks answer as for a run that is not
    going until ``job_restored``.
    """

    kind: Literal[EventKind.JOB_HELD] = EventKind.JOB_HELD
    withdrawn: list[str] = []
    kept: dict[str, str] = {}


class JobRestoredEvent(_ExecutionEvent):
    """A held job put back what it withdrew and goes on.

    ``restored`` are the contract definitions created again; ``lost`` the ones
    the connector would not take back, with why.
    """

    kind: Literal[EventKind.JOB_RESTORED] = EventKind.JOB_RESTORED
    restored: list[str] = []
    lost: dict[str, str] = {}


class StepSuspendedEvent(_ExecutionEvent):
    """A wait stopped counting because its job was paused.

    ``remaining_s`` is what is left of its timeout, and what it waits for once
    the job resumes — announced then by a fresh ``step_waiting`` carrying it as
    ``timeout_s``. ``waited_ms`` is how long it had been waiting, across every
    stretch so far.
    """

    kind: Literal[EventKind.STEP_SUSPENDED] = EventKind.STEP_SUSPENDED
    test_id: str
    step_id: str | None = None
    step_type: str
    listener: Listener
    remaining_s: float
    waited_ms: int

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

"""Enumerations used across the Testlab module."""

from __future__ import annotations

import enum


class StepStatus(str, enum.Enum):
    """Execution status of an individual test step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ScriptStatus(str, enum.Enum):
    """Execution status of a test script."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class JobStatus(str, enum.Enum):
    """Overall status of a test execution job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


class AssertionSeverity(str, enum.Enum):
    """Whether assertion failure aborts (HARD) or just warns (SOFT)."""

    HARD = "HARD"
    SOFT = "SOFT"


class ValueSource(str, enum.Enum):
    """Origin of a parameter value (inline literal, file, or variable reference)."""

    INLINE = "INLINE"
    FILE = "FILE"
    VARIABLE = "VARIABLE"


class VariableSource(str, enum.Enum):
    """How a declared variable obtains its value (LOCKED GRAMMAR v1).

    ``VALUE`` is a literal provided now, ``INPUT`` is asked from the operator at
    runtime, and ``GENERATED`` is produced by a named generator.
    """

    VALUE = "value"
    INPUT = "input"
    GENERATED = "generated"


class VariableScope(str, enum.Enum):
    """Identifies which participant is responsible for providing a runtime input variable.

    ``ENGINE`` means the TestLab engine operator supplies the value (e.g. connector
    management URL). ``SUT`` means the System-Under-Test operator supplies the value
    (e.g. provider BPN-L).

    Only meaningful when ``source: input``; variables with ``source: value`` or
    ``source: generated`` leave ``scope`` as ``None``.
    """

    ENGINE = "engine"
    SUT = "sut"


class SdkCallMode(str, enum.Enum):
    """Controls which SDK calls are permitted during execution."""

    ALLOWLIST = "ALLOWLIST"
    OPEN = "OPEN"


class ServiceType(str, enum.Enum):
    """Type of dataspace service a participant can expose."""

    CONNECTOR_CONSUMER = "CONNECTOR_CONSUMER"
    CONNECTOR_PROVIDER = "CONNECTOR_PROVIDER"
    DTR = "DTR"
    EDC_CONNECTOR = "EDC_CONNECTOR"
    EDC_CONNECTOR_SATURN = "EDC_CONNECTOR_SATURN"
    EDC_CONNECTOR_JUPITER = "EDC_CONNECTOR_JUPITER"
    DIGITAL_TWIN_REGISTRY = "DIGITAL_TWIN_REGISTRY"
    DISCOVERY_FINDER = "DISCOVERY_FINDER"


class PackageFormat(str, enum.Enum):
    """Format used for compiled test packages."""

    PLAIN = "PLAIN"
    ENCRYPTED = "ENCRYPTED"


class ServiceState(str, enum.Enum):
    """Lifecycle state of a managed service instance."""

    DECLARED = "DECLARED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class StepPhase(str, enum.Enum):
    """Identifies which execution phase a step belongs to."""

    SETUP = "SETUP"
    EXECUTION = "EXECUTION"
    TEARDOWN = "TEARDOWN"


class ScriptKind(str, enum.Enum):
    """Explicit type discriminator for YAML files, following the Kubernetes ``kind:`` convention."""

    TEST = "test"
    TCK = "tck"


class EventKind(str, enum.Enum):
    """Discriminator identifying the semantic kind of an execution event.

    Every event published by the execution engine's :class:`ExecutionMonitor`
    carries its ``kind`` so a consumer (IDE, CLI, log sink) can decide what
    happened by reading this field directly, instead of sniffing ``step_type``
    or other free-text values. The SSE wire event name is derived from the
    kind value by turning its single underscore into a dot, e.g.
    ``step_completed`` -> ``step.completed``.
    """

    JOB_STARTED = "job_started"
    JOB_PAUSED = "job_paused"
    JOB_RESUMED = "job_resumed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    SCRIPT_STARTED = "script_started"
    SCRIPT_COMPLETED = "script_completed"
    STEP_STARTED = "step_started"
    STEP_CALL = "step_call"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"
    STEP_WAITING = "step_waiting"
    ASSERTION_RESULT = "assertion_result"

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""
Testlab data models package.

Re-exports all public symbols so that ``from tractusx_testlab.models import X``
continues to work unchanged.
"""

from tractusx_testlab.models.authoring.definitions import (
    Assertion,
    EnvDefinition,
    ImportDefinition,
    MetadataDefinition,
    ReturnFieldDefinition,
    ServiceDefinition,
    StepDefinition,
    TckDefinition,
    TckMetadataDefinition,
    TestDefinition,
    VariableDefinition,
)
from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    DataspaceContext,
    InfrastructureConfig,
    Standard,
)
from tractusx_testlab.models.domain.infrastructure import (
    CapabilityBinding,
    ConnectorBinding,
    DtrBinding,
    EngineBindings,
    EngineDtrBinding,
    Infrastructure,
    SutBindings,
    SutConnectorBinding,
)
from tractusx_testlab.models.domain.security import (
    Base64Bytes,
    EncryptedKeyBlock,
    PackageManifest,
    SecurityBlock,
)
from tractusx_testlab.models.domain.server import (
    UploadedPackage,
    VaultConfig,
)
from tractusx_testlab.models.primitives.binding_errors import (
    InfrastructureError,
    MissingBindingError,
    MissingInputVariableError,
    StandardConflictError,
    UnknownBindingKeyError,
)
from tractusx_testlab.models.primitives.enums import (
    AssertionSeverity,
    DefinitionKind,  # local override — adds TCK
    EventKind,
    JobStatus,
    PackageFormat,
    SdkCallMode,
    ServiceState,
    ServiceType,  # local override — adds EDC connector types
    StepPhase,
    StepStatus,
    TestStatus,
    ValueSource,
    VariableScope,  # verb-form variable scope
    VariableSource,  # verb-form variable source
)
from tractusx_testlab.models.primitives.exceptions import (
    AuthoringError,
    BoundServiceError,
    ConnectorError,
    EngineError,
    ExecutionError,
    NoAssertionsExecutedError,
    SkipNotAllowedError,
    StepConfigError,
    StepExecutionError,
    TestLabError,
    UnresolvedReferenceError,
    VariableTypeError,
)
from tractusx_testlab.models.primitives.service_errors import (
    DuplicateServiceError,
    ServiceInitError,
    ServiceNotFoundError,
    ServiceNotReadyError,
    ServiceTypeMismatchError,
)
from tractusx_testlab.models.runtime.events import (
    AssertionResultEvent,
    ExecutionEvent,
    JobCancelledEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobPausedEvent,
    JobResumedEvent,
    JobStartedEvent,
    Listener,
    StepCallEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepListeningEvent,
    StepReceivedEvent,
    StepSkippedEvent,
    StepStartedEvent,
    StepWaitingEvent,
    TestCompletedEvent,
    TestStartedEvent,
)
from tractusx_testlab.models.runtime.inspection import (
    StepMeta,
    TckInspectionResult,
    TestInspection,
)
from tractusx_testlab.models.runtime.jobs import (
    Job,
    JobEvent,
    JobMemory,
)
from tractusx_testlab.models.runtime.results import (
    AssertionResult,
    AssertionSummary,
    CallbackResult,
    HttpExchange,
    HttpRequest,
    HttpResponse,
    StepResult,
    TckResult,
    TestResult,
)

__all__ = [
    # definitions
    "Assertion",
    # results
    "AssertionResult",
    # execution events
    "AssertionResultEvent",
    # enums
    "AssertionSeverity",
    "AssertionSummary",
    # exceptions
    "AuthoringError",
    # security
    "Base64Bytes",
    "BoundServiceError",
    "CallbackResult",
    # infrastructure bindings (operated)
    "CapabilityBinding",
    # infrastructure requirements (authored)
    "CapabilityRequirement",
    "ConnectorBinding",
    "ConnectorError",
    "DataspaceContext",
    "DefinitionKind",
    "DtrBinding",
    "DuplicateServiceError",
    "EncryptedKeyBlock",
    "EngineBindings",
    "EngineDtrBinding",
    "EngineError",
    "EnvDefinition",
    "EventKind",
    "ExecutionError",
    "ExecutionEvent",
    "HttpExchange",
    "HttpRequest",
    "HttpResponse",
    "ImportDefinition",
    "Infrastructure",
    "InfrastructureConfig",
    "InfrastructureError",
    # jobs
    "Job",
    "JobCancelledEvent",
    "JobCompletedEvent",
    "JobEvent",
    "JobFailedEvent",
    "JobMemory",
    "JobPausedEvent",
    "JobResumedEvent",
    "JobStartedEvent",
    "JobStatus",
    "Listener",
    "MetadataDefinition",
    "MissingBindingError",
    "MissingInputVariableError",
    "NoAssertionsExecutedError",
    "PackageFormat",
    "PackageManifest",
    "ReturnFieldDefinition",
    "SdkCallMode",
    "SecurityBlock",
    "ServiceDefinition",
    "ServiceInitError",
    "ServiceNotFoundError",
    "ServiceNotReadyError",
    "ServiceState",
    "ServiceType",
    "ServiceTypeMismatchError",
    "SkipNotAllowedError",
    "Standard",
    "StandardConflictError",
    "StepCallEvent",
    "StepCompletedEvent",
    "StepConfigError",
    "StepDefinition",
    "StepExecutionError",
    "StepFailedEvent",
    "StepListeningEvent",
    "StepMeta",
    "StepPhase",
    "StepReceivedEvent",
    "StepResult",
    "StepSkippedEvent",
    "StepStartedEvent",
    "StepStatus",
    "StepWaitingEvent",
    "SutBindings",
    "SutConnectorBinding",
    "TckDefinition",
    "TckInspectionResult",
    "TckMetadataDefinition",
    "TckResult",
    "TestCompletedEvent",
    "TestDefinition",
    # inspection
    "TestInspection",
    "TestLabError",
    "TestResult",
    "TestStartedEvent",
    "TestStatus",
    "UnknownBindingKeyError",
    "UnresolvedReferenceError",
    # server
    "UploadedPackage",
    "ValueSource",
    "VariableDefinition",
    "VariableScope",
    "VariableSource",
    "VariableTypeError",
    "VaultConfig",
]

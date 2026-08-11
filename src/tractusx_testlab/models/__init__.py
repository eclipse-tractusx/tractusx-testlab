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
    ScriptDefinition,
    ScriptDefinition,
    ServiceDefinition,
    StepDefinition,
    TckDefinition,
    TckDefinition,
    TckMetadataDefinition,
    VariableDefinition,
)
from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    DataspaceContext,
    InfrastructureConfig,
    Standard,
)
from tractusx_testlab.models.primitives.enums import (
    AssertionSeverity,
    FailurePolicy,
    JobStatus,
    PackageFormat,
    ScriptStatus,
    SdkCallMode,
    ServiceState,
    StepStatus,
    ValueSource,
)
from tractusx_testlab.models.primitives.enums import VariableSource  # verb-form variable source
from tractusx_testlab.models.primitives.enums import VariableScope  # verb-form variable scope
from tractusx_testlab.models.primitives.enums import AssertionType  # local override — adds typed assertion types
from tractusx_testlab.models.primitives.enums import ScriptKind  # local override — adds TCK
from tractusx_testlab.models.primitives.enums import ServiceType  # local override — adds EDC connector types
from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.primitives.exceptions import (
    DuplicateServiceError,
    ServiceInitError,
    ServiceNotFoundError,
    ServiceNotReadyError,
    ServiceTypeMismatchError,
    SkipNotAllowedError,
    StepConfigError,
)
from tractusx_testlab.models.runtime.jobs import (
    Job,
    JobEvent,
    JobMemory,
)
from tractusx_testlab.models.runtime.inspection import (
    ScriptInspection,
    StepMeta,
    TckInspectionResult,
)
from tractusx_testlab.models.runtime.results import (
    AssertionResult,
    AssertionSummary,
    CallbackResult,
    HttpRequest,
    HttpResponse,
    ScriptResult,
    StepResult,
    TckResult
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

__all__ = [
    # enums
    "AssertionSeverity",
    "AssertionType",
    "FailurePolicy",
    "JobStatus",
    "PackageFormat",
    "ScriptKind",
    "ScriptStatus",
    "SdkCallMode",
    "ServiceState",
    "ServiceType",
    "StepPhase",
    "StepStatus",
    "ValueSource",
    "VariableScope",
    # infrastructure
    "CapabilityRequirement",
    "DataspaceContext",
    "InfrastructureConfig",
    "Standard",
    # definitions
    "Assertion",
    "EnvDefinition",
    "ImportDefinition",
    "MetadataDefinition",
    "ReturnFieldDefinition",
    "ScriptDefinition",
    "ScriptDefinition",
    "ServiceDefinition",
    "StepDefinition",
    "TckDefinition",
    "TckDefinition",
    "TckMetadataDefinition",
    "VariableDefinition",
    "VariableSource",
    # security
    "Base64Bytes",
    "EncryptedKeyBlock",
    "PackageManifest",
    "SecurityBlock",
    # server
    "UploadedPackage",
    "VaultConfig",
    # inspection
    "ScriptInspection",
    "StepMeta",
    "TckInspectionResult",
    # results
    "AssertionResult",
    "AssertionSummary",
    "CallbackResult",
    "HttpRequest",
    "HttpResponse",
    "ScriptResult",
    "StepResult",
    "TckResult",
    # jobs
    "Job",
    "JobEvent",
    "JobMemory",
    # exceptions
    "DuplicateServiceError",
    "ServiceInitError",
    "ServiceNotFoundError",
    "ServiceNotReadyError",
    "ServiceTypeMismatchError",
    "SkipNotAllowedError",
    "StepConfigError",
]

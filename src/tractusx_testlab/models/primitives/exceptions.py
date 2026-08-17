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

"""Service exceptions for the Testlab module."""

from __future__ import annotations

from tractusx_testlab.models.primitives.enums import ServiceState, ServiceType


class ServiceNotFoundError(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Service not found: {name}")


class ServiceNotReadyError(Exception):
    def __init__(self, name: str, state: ServiceState):
        self.name = name
        self.state = state
        super().__init__(f"Service '{name}' is in state {state.value}, not READY")


class ServiceTypeMismatchError(Exception):
    def __init__(self, step_type: str, expected: ServiceType, actual: ServiceType):
        self.step_type = step_type
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Step '{step_type}' expects {expected.value} but got {actual.value}"
        )


class StepConfigError(Exception):
    def __init__(self, step_type: str, message: str):
        self.step_type = step_type
        super().__init__(f"Step config error in '{step_type}': {message}")


class SkipNotAllowedError(Exception):
    """Raised when the operator requests skipping a test not marked ``skippable: true``.

    The error is raised before the run starts so the operator can correct the
    request without any test having executed.
    """

    def __init__(self, test_ids: list[str], reason: str = "not marked skippable") -> None:
        self.test_ids = test_ids
        ids_str = ", ".join(f"'{t}'" for t in test_ids)
        super().__init__(
            f"Cannot skip test(s) {ids_str}: {reason}. "
            f"Set skippable: true on the test entry in the TCK manifest to allow skipping."
        )


class InfrastructureError(Exception):
    """Base for problems with the infrastructure bindings an engine was given."""


class UnknownBindingKeyError(InfrastructureError):
    """Raised when a binding key names no field of the infrastructure model.

    A misspelled key used to be dropped in silence and surface as an empty URL
    several steps later, so the key is rejected where it is written and the
    accepted ones are listed beside it.
    """

    def __init__(self, key: str, known: list[str]) -> None:
        self.key = key
        self.known = known
        listed = "\n  ".join(known)
        super().__init__(
            f"Unknown infrastructure binding key: '{key}'. Accepted keys are:\n  {listed}"
        )


class MissingBindingError(InfrastructureError):
    """Raised before the first step when a required capability was never bound.

    Reports every unbound capability at once, each with the key the operator
    still owes, so one run tells them everything they have to supply.
    """

    def __init__(self, missing: list[tuple[str, str, str]]) -> None:
        self.missing = missing
        lines = "\n".join(
            f"  {side}.{capability} — set '{key}' "
            f"(or {'TESTLAB_' + key.split('.', 1)[1].replace('.', '_').upper()})"
            for side, capability, key in missing
        )
        capabilities = ", ".join(f"{side}.{capability}" for side, capability, _ in missing)
        super().__init__(
            f"This TCK requires infrastructure that is not bound: {capabilities}\n{lines}"
        )


class StandardConflictError(InfrastructureError):
    """Raised when a binding claims a different standard or release than the TCK certifies.

    A TCK that certifies against Saturn cannot prove anything by running
    against a connector the operator declared as Jupiter — one of the two is
    wrong, and which one is the operator's call, so both are printed.
    """

    def __init__(self, conflicts: list[tuple[str, str, str, str, str]]) -> None:
        self.conflicts = conflicts
        lines = "\n".join(
            f"  {side}.{capability}.{field}: bound as '{bound}', "
            f"but this TCK certifies against '{required}'"
            for side, capability, field, bound, required in conflicts
        )
        super().__init__(
            "The infrastructure bound does not match what this TCK certifies against:\n"
            f"{lines}"
        )


class DuplicateServiceError(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Duplicate service name: {name}")


class ServiceInitError(Exception):
    def __init__(self, name: str, cause: Exception):
        self.name = name
        self.cause = cause
        super().__init__(f"Failed to initialize service '{name}': {cause}")

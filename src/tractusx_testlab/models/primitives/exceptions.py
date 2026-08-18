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

"""Everything TestLab raises, and the three questions the hierarchy answers.

A conformance engine has to distinguish three outcomes that look alike from the
outside, because only one of them is a verdict about the system under test:

``AuthoringError``
    The TCK, or the deployment it was pointed at, is wrong. Nothing was proved
    and nothing was disproved. Raised before or instead of running a step.

``ExecutionError``
    A step ran and did not achieve what it declared. **This is a test result** —
    the SUT did not do what the TCK requires of it.

``EngineError``
    TestLab itself malfunctioned. Never a verdict: a run containing one of these
    certifies nothing, whatever its other steps reported.

Collapsing the last two is how an engine defect gets recorded as a SUT failure,
and how a SUT failure gets excused as an engine defect. They are separated here
so the runner can classify without guessing, and so an embedder can write
``except TestLabError`` and mean it.
"""

from __future__ import annotations

from tractusx_testlab.models.primitives.enums import ServiceState, ServiceType


class TestLabError(Exception):
    """Base class for every error TestLab raises deliberately."""


class AuthoringError(TestLabError):
    """The TCK or the deployment it targets is wrong; nothing was tested."""


class ExecutionError(TestLabError):
    """A step ran and did not achieve what it declared — a result about the SUT."""


class EngineError(TestLabError):
    """TestLab malfunctioned. A run containing one of these proves nothing."""


class ServiceNotFoundError(EngineError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Service not found: {name}")


class ServiceNotReadyError(EngineError):
    def __init__(self, name: str, state: ServiceState):
        self.name = name
        self.state = state
        super().__init__(f"Service '{name}' is in state {state.value}, not READY")


class ServiceTypeMismatchError(EngineError):
    def __init__(self, step_type: str, expected: ServiceType, actual: ServiceType):
        self.step_type = step_type
        self.expected = expected
        self.actual = actual
        super().__init__(f"Step '{step_type}' expects {expected.value} but got {actual.value}")


class StepConfigError(AuthoringError):
    def __init__(self, step_type: str, message: str):
        self.step_type = step_type
        super().__init__(f"Step config error in '{step_type}': {message}")


class SkipNotAllowedError(AuthoringError):
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


class InfrastructureError(AuthoringError):
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
            f"The infrastructure bound does not match what this TCK certifies against:\n{lines}"
        )


class DuplicateServiceError(EngineError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Duplicate service name: {name}")


class ServiceInitError(EngineError):
    def __init__(self, name: str, cause: Exception):
        self.name = name
        self.cause = cause
        super().__init__(f"Failed to initialize service '{name}': {cause}")


class UnresolvedReferenceError(AuthoringError):
    """Raised when a ``${{ ... }}`` reference names nothing the run can supply.

    The reference used to be left as its own template text and handed to the
    step as data, so a URL built from an undefined variable was requested
    verbatim and a comparison against one compared against a string containing
    braces. Neither failed; both produced a verdict about a SUT that was never
    asked the question.

    The variables in scope are listed because the usual cause is a name that
    exists under a different spelling, and the author cannot see the namespace
    from the script.
    """

    def __init__(self, reference: str, available: list[str] | None = None) -> None:
        self.reference = reference
        self.available = available or []
        listed = ", ".join(sorted(self.available)[:20]) or "nothing"
        more = "" if len(self.available) <= 20 else f" (and {len(self.available) - 20} more)"
        super().__init__(f"'{reference}' resolves to nothing. In scope: {listed}{more}.")


class StepExecutionError(ExecutionError):
    """Raised when a step could not achieve the output it declares.

    Steps used to report this by fabricating an ``HttpResponse(status_code=500)``
    and returning normally, which the runner recorded as PASSED — the status
    code was invented rather than observed, and nothing downstream read it.
    """

    def __init__(self, step_type: str, reason: str) -> None:
        self.step_type = step_type
        super().__init__(f"{step_type}: {reason}")


class NoAssertionsExecutedError(ExecutionError):
    """Raised when a script declared checks and ran none of them.

    Not "a TCK with no assertions is invalid" — a provisioning-only TCK is
    legitimate. This is the narrower and unambiguous case: the author wrote
    ``validate:`` entries and zero of them were evaluated, so the run reported
    on a SUT it never actually checked.
    """

    def __init__(self, script: str, declared: int) -> None:
        self.script = script
        self.declared = declared
        super().__init__(
            f"Script '{script}' declared {declared} assertion(s) and executed none. "
            f"The run cannot certify anything it did not check."
        )

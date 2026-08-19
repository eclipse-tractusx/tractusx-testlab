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

from typing import Any

from tractusx_testlab.models.primitives.enums import ServiceState, ServiceType


class TestLabError(Exception):
    """Base class for every error TestLab raises deliberately.

    An error may also *name* itself and carry the evidence behind it.
    ``code`` is the machine-readable name the trace publishes as
    ``errors[].code`` and ``diagnostics`` is what a reader needs in order to act
    on it — the offers that were compared, the states that were polled — which
    the trace publishes as ``errors[].context`` (ADR-0016). Both default to
    nothing, so an error with only a sentence to say stays a one-line class, and
    the sentence is still all the trace carries.
    """

    #: Machine-readable name of this failure, or ``None`` to be classified by
    #: origin alone (``STEP_FAILED`` for a verdict, ``ENGINE_FAULT`` for a bug).
    code: str | None = None

    #: Structured evidence for the message, published under the error's
    #: ``context``. JSON-serialisable, because that is where it ends up.
    diagnostics: dict[str, Any] | None = None


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

    When the reference reaches *into* something that is in scope, the message
    says so and names the fix. A reference is a name, not a path: the walk into
    a step's output happens once, in that step's ``returns:``, and the declared
    name is what a later step reads. Someone who writes
    ``${{ execution.call.body.kind }}`` against a step that declared ``body``
    has made one specific mistake with one specific remedy, and a bare list of
    everything in scope leaves them to infer the rule from it.
    """

    def __init__(self, reference: str, available: list[str] | None = None) -> None:
        self.reference = reference
        self.available = available or []
        listed = ", ".join(sorted(self.available)[:20]) or "nothing"
        more = "" if len(self.available) <= 20 else f" (and {len(self.available) - 20} more)"
        super().__init__(
            f"'{reference}' resolves to nothing.{self._remedy()} In scope: {listed}{more}."
        )

    def _remedy(self) -> str:
        """Name the fix when the reference reaches into something in scope."""
        segments = self.reference.split(".")
        for cut in range(len(segments) - 1, 0, -1):
            prefix, rest = ".".join(segments[:cut]), ".".join(segments[cut:])
            if prefix not in self.available:
                continue
            owner = ".".join(prefix.split(".")[2:]) or prefix
            return (
                f" '{prefix}' is in scope but '{rest}' is a path into its value,"
                f" and a reference is a name rather than a path. Declare it as"
                f" `returns: {{ {owner}.{rest}: ... }}` on the step that produces"
                f" it, then reference '{self.reference}'."
            )
        return ""


class VariableTypeError(AuthoringError):
    """Raised when an ``env`` variable's value cannot be read as the type it declares.

    ``returns.<key>.type`` is the variable's contract with every step that reads
    it, and YAML alone cannot keep it: a policy written as a ``value: |`` block
    is text, and it used to be seeded as text under a declaration saying
    ``object``. Steps compensated one at a time — the connector steps parse JSON
    out of a policy string — and the ones that did not saw a string where the
    manifest promised a mapping.

    The declaration decides instead, so this is the narrow case left over: a
    variable declaring a structure, written as text that is not the structure it
    declares — the text is read as YAML, so a pasted JSON document parses as
    readily as an unindented block. It is refused where it is written rather
    than handed on as a value that reads wrong several steps later.
    """

    def __init__(self, name: str, declared: str, reason: str) -> None:
        self.name = name
        self.declared = declared
        shape = "a mapping" if declared == "object" else "a list"
        super().__init__(
            f"Variable '{name}' declares 'type: {declared}' and its value {reason}. "
            f"Write it under 'with.value' as {shape} — inline, or as JSON or YAML "
            f"text in a 'value: |' block."
        )


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

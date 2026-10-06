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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.
"""The two ways a step's or a test's run ends without the verdict it declared.

Both are :class:`ExecutionError` — a result about the system under test, not a
defect of the TCK or of TestLab — and kept apart from the hierarchy in
:mod:`tractusx_testlab.models.primitives.exceptions` only for length.
"""

from __future__ import annotations

from tractusx_testlab.models.primitives.exceptions import ExecutionError

__all__ = ["NoAssertionsExecutedError", "StepExecutionError"]


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
    """Raised when a test declared checks and ran none of them.

    Not "a TCK with no assertions is invalid" — a provisioning-only TCK is
    legitimate. This is the narrower and unambiguous case: the author wrote
    ``validate:`` entries and zero of them were evaluated, so the run reported
    on a SUT it never actually checked.
    """

    def __init__(self, test: str, declared: int) -> None:
        self.test = test
        self.declared = declared
        super().__init__(
            f"Test '{test}' declared {declared} assertion(s) and executed none. "
            f"The run cannot certify anything it did not check."
        )

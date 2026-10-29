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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A check step's findings, reported as checks of the step. **Experimental.**

A check step keeps its output — the verdict and every problem — and fails
through its checks, the channel a flow step reports its sub-steps' checks on:
one check per category (``status``, ``body``, …, or one per operation of a
sweep), each with the problems it found. The step's output therefore survives
a failure, and the report says which check failed and why.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from tractusx_testlab.models import AssertionResult
from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.openapi.conformance import Problem
from tractusx_testlab.steps.flow._nested import NestedChecks

#: Problems quoted in one check's message; all of them stay in ``actual``.
MESSAGE_PROBLEMS = 5


def described(problem: Problem) -> str:
    """One problem as a line of a message: where, what, which keyword where."""
    where = f"{problem.pointer or '<root>'}: " if problem.pointer is not None else ""
    keyword = (
        f" (keyword '{problem.keyword}' at {problem.schema_location})"
        if problem.keyword and problem.schema_location
        else ""
    )
    received = f"; received {problem.received}" if problem.received else ""
    return f"{where}{problem.message}{keyword}{received}"


def summary(problems: Sequence[Problem]) -> str:
    """Up to :data:`MESSAGE_PROBLEMS` problems as one message, with how many more."""
    lines = [described(problem) for problem in problems[:MESSAGE_PROBLEMS]]
    more = len(problems) - MESSAGE_PROBLEMS
    return "; ".join(lines) + (f"; and {more} more" if more > 0 else "")


def check(
    uses: str, name: str, problems: Sequence[Problem], expected: Any = None
) -> AssertionResult:
    """One check named *name*: passed when *problems* is empty."""
    return AssertionResult(
        assertion=Assertion(uses=uses, name=name),
        passed=not problems,
        expected=expected,
        actual=[problem.as_dict() for problem in problems] or None,
        message=summary(problems),
    )


def nested(uses: str, checks: Iterable[tuple[str, Sequence[Problem]]]) -> NestedChecks:
    """The checks of a check step, ready for ``StepOutput.nested``."""
    results = [check(uses, name, problems) for name, problems in checks]
    return NestedChecks(results, len(results))

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

"""Holding every ``validate:`` entry's ``severity`` to ``HARD`` or ``SOFT``.

The value used to be read only at run time, so ``severity: warning`` compiled
cleanly and then stopped the run with a ``ValueError`` from the enum. The case
is free — ``soft`` is ``SOFT`` — but no other word is a severity.
"""

from __future__ import annotations

from collections.abc import Iterator

from tractusx_testlab.compiler.validation._variable_references import nested_steps
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.assertions.vocabulary import check_severity
from tractusx_testlab.syntax import keys, patterns


def severity_findings(step_def: StepDefinition, step_cls: type | None) -> Iterator[tuple[str, str]]:
    """Every ``(field, message)`` for a severity in *step_def* that names nothing.

    Nested steps run their own ``validate:`` entries, so theirs are checked as
    well, each located under the path it sits at. A ``${{ ... }}`` value is
    known only at run time, where the engine reports a bad one as a failed check.
    """
    for where, withs in _validate_blocks(step_def, step_cls):
        for index, params in enumerate(withs):
            if not isinstance(params, dict) or keys.SEVERITY not in params:
                continue
            value = params[keys.SEVERITY]
            if isinstance(value, str) and patterns.EXPR_REF.search(value):
                continue
            problem = check_severity(value)
            if problem:
                yield f"{where}validate[{index}].with.severity", problem


def _validate_blocks(
    step_def: StepDefinition, step_cls: type | None
) -> Iterator[tuple[str, list[object]]]:
    """Each ``validate:`` block the step runs, as ``(where, [with, ...])``.

    The step's own block is at ``""``; a nested step's is at the path it sits
    under, e.g. ``with.steps[0].``.
    """
    yield "", [assertion.with_ for assertion in step_def.assertions or []]
    for where, nested in nested_steps(step_cls, step_def.with_):
        entries = nested.get(keys.EXPECT)
        if isinstance(entries, list):
            yield f"{where}.", [e.get(keys.WITH) if isinstance(e, dict) else None for e in entries]

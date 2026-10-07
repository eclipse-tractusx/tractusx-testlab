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


"""How many checks a test's steps asked for — what its summary measures against."""

from __future__ import annotations

from tractusx_testlab.authoring.test import Test
from tractusx_testlab.models import StepStatus
from tractusx_testlab.models.runtime.results import StepResult


def declared_checks(test: Test, results: list[StepResult]) -> int:
    """Count the assertions the steps that actually ran had asked for.

    Steps skipped by ``if:`` are excluded: a check that was never reached was
    not dropped, it was correctly not applicable. A flow step's sub-steps are
    not in the test's phases: the flow step counted what the ones that ran
    declared (``StepResult.nested_declared``), and a branch not taken declared
    nothing.
    """
    ran = {result.step_type for result in results if result.status is not StepStatus.SKIPPED}
    own = sum(
        len(step.assertions or [])
        for phase in (
            test.definition.setup,
            test.definition.execution,
            test.definition.teardown,
        )
        for step in phase
        if step.uses in ran
    )
    return own + sum(result.nested_declared for result in results)

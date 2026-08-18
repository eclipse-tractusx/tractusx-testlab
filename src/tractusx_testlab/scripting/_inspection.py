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

"""Pure helper — maps a loaded Tck into a TckInspectionResult.

This module mirrors the pattern of ``scripting/_variable_form.py``:
a side-effect-free function that is called by ``Tck.inspect()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models.primitives.enums import StepPhase
from tractusx_testlab.models.runtime.inspection import (
    ScriptInspection,
    StepMeta,
    TckInspectionResult,
)

if TYPE_CHECKING:
    from tractusx_testlab.scripting.script import Tck


def build_inspection_result(tck: Tck) -> TckInspectionResult:
    """Extract static metadata from *tck* without executing any steps.

    Args:
        tck: The :class:`~tractusx_testlab.scripting.script.Tck` to describe.

    Returns:
        A frozen :class:`TckInspectionResult` with general and step-level metadata.
    """
    script_inspections: list[ScriptInspection] = []

    for script in tck.scripts:
        step_metas: list[StepMeta] = []
        step_metas.extend(_map_steps(script.setup, StepPhase.SETUP))
        step_metas.extend(_map_steps(script.steps, StepPhase.EXECUTION))
        step_metas.extend(_map_steps(script.teardown, StepPhase.TEARDOWN))
        script_inspections.append(
            ScriptInspection(name=script.name, test_id=script.test_id, skippable=script.skippable, steps=tuple(step_metas))
        )

    total_steps = sum(len(s.steps) for s in script_inspections)
    total_validations = sum(
        sm.validation_count for s in script_inspections for sm in s.steps
    )

    return TckInspectionResult(
        name=tck.name,
        total_steps=total_steps,
        total_validations=total_validations,
        scripts=tuple(script_inspections),
    )


def _map_steps(step_defs: list, phase: StepPhase) -> list[StepMeta]:
    """Convert a list of StepDefinition objects into StepMeta instances."""
    return [
        StepMeta(
            step_name=step.name or step.uses,
            uses=step.uses,
            phase=phase,
            validation_count=len(step.assertions or []),
        )
        for step in step_defs
    ]

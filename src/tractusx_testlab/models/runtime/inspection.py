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

"""Inspection result models — static metadata extracted from a loaded Tck."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tractusx_testlab.models.primitives.enums import StepPhase


class StepMeta(BaseModel):
    """Metadata for a single step extracted without executing it."""

    model_config = ConfigDict(frozen=True)

    step_name: str
    uses: str
    phase: StepPhase
    validation_count: int


class ScriptInspection(BaseModel):
    """Inspection result for a single script within a TCK."""

    model_config = ConfigDict(frozen=True)

    name: str
    test_id: str = ""
    skippable: bool = False
    steps: tuple[StepMeta, ...]


class TckInspectionResult(BaseModel):
    """Aggregated static metadata extracted from a Tck without executing it."""

    model_config = ConfigDict(frozen=True)

    name: str
    total_steps: int
    total_validations: int
    scripts: tuple[ScriptInspection, ...]

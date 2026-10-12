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

"""The machine-readable description of a step's interface (``BaseStep.describe``)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tractusx_testlab.models.primitives.checkpoint import Checkpoint


class StepContract(BaseModel):
    """Machine-readable description of a step's declared interface.

    Produced by :meth:`BaseStep.describe` for documentation generation and
    test validation.  Both schemas are always present, because every step
    declares its inputs and its output. ``checkpoint`` is the step type's
    checkpoint declaration (ADR-0028), ``None`` for a step that is not one.
    """

    step_type: str = ""
    description: str = ""
    params_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    checkpoint: Checkpoint | None = None

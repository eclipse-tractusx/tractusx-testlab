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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""ADR-0019 topology models: the ``dataspace`` and ``infrastructure`` blocks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from tractusx_testlab.models.domain.infrastructure import capability_keys

# The two bindable sides of the topology (ADR-0019 §1).
SideKey = Literal["engine", "sut"]


class DataspaceContext(BaseModel):
    """The ecosystem context a run targets — the single source of the version."""

    model_config = ConfigDict(frozen=True)

    ecosystem: str
    version: str


class Standard(BaseModel):
    """Optional standard constraint on a capability (ADR-0019 §1)."""

    model_config = ConfigDict(frozen=True)

    id: str
    version: str | None = None

    def effective_version(self, dataspace_version: str) -> str:
        """Resolve the constraint version, inheriting ``dataspace.version`` when omitted."""
        return self.version or dataspace_version


class CapabilityRequirement(BaseModel):
    """One capability requirement: an explicit ``required`` flag plus an optional standard."""

    model_config = ConfigDict(frozen=True)

    required: bool
    standard: Standard | None = None


class InfrastructureConfig(BaseModel):
    """The two bindable sides, each keyed by capability (ADR-0019 §1).

    Which capabilities a side accepts is not restated here: it is read from the
    binding model, which is the registry. The sides are asymmetric by design,
    so each is checked against its own side's capabilities, and a TCK naming
    one the engine cannot bind is refused while the manifest is parsed rather
    than at the step that needed it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    engine: dict[str, CapabilityRequirement] = Field(default_factory=dict)
    sut: dict[str, CapabilityRequirement] = Field(default_factory=dict)

    @field_validator("engine", "sut")
    @classmethod
    def _known_capabilities(
        cls,
        declared: dict[str, CapabilityRequirement],
        info: ValidationInfo,
    ) -> dict[str, CapabilityRequirement]:
        """Reject a capability the binding model has no field for on this side."""
        side = info.field_name
        accepted = capability_keys(side)
        unknown = [key for key in declared if key not in accepted]
        if unknown:
            raise ValueError(
                f"Unknown capability on side '{side}': {', '.join(sorted(unknown))}. "
                f"Accepted on this side: {', '.join(accepted)}"
            )
        return declared

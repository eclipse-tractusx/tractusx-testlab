################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The topology a run targets — which capabilities each side of it has.

This is the *binding* half of ADR-0019, and the counterpart of
:mod:`tractusx_testlab.models.authoring.infrastructure`, which models the
*requirement* half. A requirement is authored into a TCK and says a capability
is needed; a binding is supplied by whoever operates the engine and says where
that capability lives. The two meet once per run, when the player checks every
required capability against the bindings it was given.

The capability types themselves are in
:mod:`tractusx_testlab.models.domain.capabilities`. What this module adds is
the arrangement: which capabilities the engine has, which the SUT has, and the
registry :func:`capability_bindings` derives from that arrangement — the single
place anything else reads to learn what capabilities exist at all.

The submodel server is not a capability of its own: a registry entry is a
pointer to a payload, so the backend those payloads live on is part of the
registry the engine operates and is bound as a field of it
(``engine.dtr.submodel_base_url``). It is engine-side only, because the engine
hosts the data a test provisions and a test that could name its own server
would be testing an address rather than the provider's backend.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tractusx_testlab.models.domain.capabilities import (
    CapabilityBinding,
    ConnectorBinding,
    DtrBinding,
    EngineDtrBinding,
    SutConnectorBinding,
)

__all__ = [
    "CapabilityBinding",
    "ConnectorBinding",
    "DtrBinding",
    "EngineBindings",
    "EngineDtrBinding",
    "Infrastructure",
    "SutBindings",
    "SutConnectorBinding",
    "capability_bindings",
    "capability_keys",
]


class EngineBindings(BaseModel):
    """Infrastructure the engine operates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector: ConnectorBinding = Field(default_factory=ConnectorBinding)
    dtr: EngineDtrBinding = Field(default_factory=EngineDtrBinding)


class SutBindings(BaseModel):
    """Infrastructure under test, which the engine only talks to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector: SutConnectorBinding = Field(default_factory=SutConnectorBinding)
    dtr: DtrBinding = Field(default_factory=DtrBinding)


class Infrastructure(BaseModel):
    """One complete deployment the engine can run a TCK against.

    An empty instance is a valid one: an engine with nothing bound can still
    run a TCK that requires nothing, and one that requires something fails
    with the capability named rather than with an empty URL.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    engine: EngineBindings = Field(default_factory=EngineBindings)
    sut: SutBindings = Field(default_factory=SutBindings)

    def binding(self, side: str, capability: str) -> CapabilityBinding | None:
        """Return the binding for *side*/*capability*, or ``None`` if that pair has none.

        The pair may legitimately not exist — the sides need not declare the
        same capabilities — which is why this answers ``None`` rather than
        raising.
        """
        side_bindings = getattr(self, side, None)
        if side_bindings is None:
            return None
        binding = getattr(side_bindings, capability, None)
        return binding if isinstance(binding, CapabilityBinding) else None

    def bound(self, side: str, capability: str) -> bool:
        """Whether *side*/*capability* is bound to a real address."""
        binding = self.binding(side, capability)
        return binding is not None and binding.is_bound()


def capability_bindings() -> tuple[tuple[str, str, type[CapabilityBinding]], ...]:
    """Return every ``(side, capability, binding_type)`` this model declares.

    The capability registry is this model and nothing else. Everything that
    needs to know which capabilities exist — the requirement keys a TCK may
    author, the config keys an operator may set, the environment and context
    projections — reads them from here, so adding a capability is adding a
    field and never also a list that has to be kept in step with it.
    """
    found: list[tuple[str, str, type[CapabilityBinding]]] = []
    for side, side_field in Infrastructure.model_fields.items():
        side_model = side_field.annotation
        if side_model is None:
            continue
        for capability, capability_field in side_model.model_fields.items():
            binding_type = capability_field.annotation
            if isinstance(binding_type, type) and issubclass(binding_type, CapabilityBinding):
                found.append((side, capability, binding_type))
    return tuple(found)


def capability_keys(side: str) -> tuple[str, ...]:
    """Return the capabilities bindable on *side*, in the order it declares them.

    Answered per side rather than as one global set: the sides are asymmetric
    by design, and a requirement may only name what its own side can bind.
    """
    return tuple(
        capability
        for declared_side, capability, _ in capability_bindings()
        if declared_side == side
    )


#: The bindable sides, in the order a reader of a config file meets them.
SIDES: tuple[str, ...] = tuple(Infrastructure.model_fields)

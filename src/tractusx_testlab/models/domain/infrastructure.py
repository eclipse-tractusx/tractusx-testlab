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

"""Infrastructure bindings — where the deployment an engine drives actually is.

This is the *binding* half of ADR-0019, and the counterpart of
:mod:`tractusx_testlab.models.authoring.infrastructure`, which models the
*requirement* half. A requirement is authored into a TCK and says a capability
is needed; a binding is supplied by whoever operates the engine and says where
that capability lives. The two meet once per run, when the player checks every
required capability against the bindings it was given.

The two sides are asymmetric on purpose (ADR-0019 §4). The **engine** side is
infrastructure TestLab operates — a connector it drives through the management
API and a registry it writes to — so it carries credentials. The **sut** side is
a counter-party TestLab only talks to, so it carries an identity and an
endpoint.

The submodel server is not a capability of its own: a registry entry is a
pointer to a payload, so the backend those payloads live on is part of the
registry the engine operates and is bound as a field of it
(``engine.dtr.submodel_base_url``). It is engine-side only, because the engine
hosts the data a test provisions and a test that could name its own server
would be testing an address rather than the provider's backend.

Every field here is one leaf of the naming rule these bindings exist to make
mechanical — a field named ``dsp_url`` on ``sut.connector`` is the config key
``sut.connector.dsp_url``, the context variable
``infrastructure.sut.connector.dsp_url``, and the environment variable
``TESTLAB_SUT_CONNECTOR_DSP_URL``, with no lookup table in between. See
:mod:`tractusx_testlab.infrastructure.mapping` for the projection itself.
"""

from __future__ import annotations

from typing import ClassVar, Optional

from pydantic import BaseModel, ConfigDict, Field


class CapabilityBinding(BaseModel):
    """One bound capability — the base every side's capabilities share.

    Bindings are frozen because a run resolves them once, before the first
    step, and every later reader must see the same deployment. They forbid
    extra fields because a misspelled key is the failure this model exists to
    turn into a message: the old string-scraped form dropped
    ``managment_url`` silently and failed twenty steps later.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Field whose presence decides whether this capability was bound at all.
    identity_field: ClassVar[str] = ""

    version: str = Field(
        default="",
        description=(
            "Ecosystem release this deployment speaks — 'saturn' or 'jupiter'. It "
            "decides which SDK dialect is built against it. Inherited from the TCK's "
            "'dataspace.version' when left empty, which is the normal case."
        ),
    )
    standard: str = Field(
        default="",
        description=(
            "Id of the Catena-X standard this capability implements, e.g. 'CX-0018' "
            "for a connector. Inherited from the TCK's requirement when left empty."
        ),
    )
    standard_version: str = Field(
        default="",
        description=(
            "Version of that standard, e.g. '2.1.3'. Inherited from the TCK's "
            "requirement when left empty."
        ),
    )

    def is_bound(self) -> bool:
        """Whether the operator supplied enough for this capability to be used.

        A capability is bound when its identifying address is present. Every
        other field qualifies an address that must already exist — an
        ``api_key`` with no connector to send it to binds nothing, and neither
        does a standard with no deployment implementing it.
        """
        return bool(str(getattr(self, self.identity_field, "") or "").strip())


class ConnectorBinding(CapabilityBinding):
    """An EDC connector, on either side of the topology."""

    identity_field: ClassVar[str] = "management_url"

    management_url: str = Field(
        default="",
        description=(
            "Management API URL of the connector, including its management path "
            "— e.g. 'https://connector.example.com/management'. The base URL and "
            "the management path are split back out of it when the SDK service is built."
        ),
    )
    api_key: str = Field(
        default="",
        description="Management API key. Empty when the connector is unauthenticated.",
    )
    api_key_header: str = Field(
        default="x-api-key",
        description="Header the management API key is sent in.",
    )
    participant_id: str = Field(
        default="",
        description="BPN-L the connector presents as its dataspace identity.",
    )
    dsp_url: str = Field(
        default="",
        description=(
            "DSP endpoint URL a counter-party negotiates against — the address "
            "catalog and negotiation steps use, not the management one."
        ),
    )
    name: str = Field(
        default="",
        description=(
            "Optional service name this connector is additionally registered under, "
            "so a script naming it explicitly resolves to the same deployment."
        ),
    )


class DtrBinding(CapabilityBinding):
    """A Digital Twin Registry, on either side of the topology."""

    identity_field: ClassVar[str] = "base_url"

    base_url: str = Field(
        default="",
        description=(
            "Root URL the registry answers on, including any ingress path prefix "
            "— e.g. 'https://registry.example.com/semantics/registry'."
        ),
    )


class EngineDtrBinding(DtrBinding):
    """The registry the engine operates, and the backend its entries point at.

    A shell descriptor is a pointer: the registry says where a submodel lives
    and something else serves it. Both halves are one deployment the operator
    stands up for the engine, so the payload backend is a field of the registry
    capability rather than a capability the TCK has to require separately.
    """

    submodel_base_url: str = Field(
        default="",
        description=(
            "Root URL submodel payloads are stored under, and the address the "
            "engine's registry entries point at. The engine addresses submodels "
            "beneath it; a script never names a server of its own."
        ),
    )


class EngineBindings(BaseModel):
    """Infrastructure the engine operates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector: ConnectorBinding = Field(default_factory=ConnectorBinding)
    dtr: EngineDtrBinding = Field(default_factory=EngineDtrBinding)


class SutBindings(BaseModel):
    """Infrastructure under test, which the engine only talks to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector: ConnectorBinding = Field(default_factory=ConnectorBinding)
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

    def binding(self, side: str, capability: str) -> Optional[CapabilityBinding]:
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
        capability for declared_side, capability, _ in capability_bindings()
        if declared_side == side
    )


#: The bindable sides, in the order a reader of a config file meets them.
SIDES: tuple[str, ...] = tuple(Infrastructure.model_fields)

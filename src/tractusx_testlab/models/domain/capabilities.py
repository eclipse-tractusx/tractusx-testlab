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

"""One bound capability, and the kinds of capability a deployment can have.

A capability is a thing the engine can talk to — a connector, a registry — and
a binding says where that thing is. The types here are the *what*; the topology
that arranges them into an engine side and a SUT side lives in
:mod:`tractusx_testlab.models.domain.infrastructure`.

The two sides are asymmetric on purpose (ADR-0019 §4). The **engine** operates
its own connector through the management API and so carries credentials; the
**sut** is a counter-party the engine only talks to, so it is identified by the
DSP endpoint it answers on. That difference is not a convention a reader has to
remember — it is :attr:`CapabilityBinding.identity_field`, and every message an
operator gets about a missing binding is derived from it.

Every field is one leaf of the naming rule these bindings exist to make
mechanical — a field named ``dsp_url`` on ``sut.connector`` is the config key
``sut.connector.dsp_url``, the context variable
``infrastructure.sut.connector.dsp_url``, and the environment variable
``TESTLAB_SUT_CONNECTOR_DSP_URL``, with no lookup table in between. See
:mod:`tractusx_testlab.infrastructure.mapping` for the projection itself.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

#: Marker a field carries when the operator must supply it themselves. Fields
#: without it either have a working default (``api_key_header``), are inherited
#: from the TCK (``version``, ``standard``), or qualify a deployment that works
#: without them (``api_key`` on an unauthenticated connector, ``name``).
OPERATOR_SUPPLIED: dict[str, Any] = {"operator_supplied": True}


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

    @classmethod
    def operator_fields(cls) -> tuple[str, ...]:
        """Return the fields the operator must supply for this capability to work.

        Read off the fields themselves rather than from a list kept beside
        them, so a field added to a binding declares its own obligation and
        the message an operator gets cannot fall behind the model.
        """
        return tuple(
            name
            for name, field in cls.model_fields.items()
            if isinstance(field.json_schema_extra, dict)
            and field.json_schema_extra.get("operator_supplied")
        )

    def missing_fields(self) -> tuple[str, ...]:
        """Return the operator-supplied fields of this binding that are still empty."""
        return tuple(
            name
            for name in type(self).operator_fields()
            if not str(getattr(self, name, "") or "").strip()
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
        json_schema_extra=OPERATOR_SUPPLIED,
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
        json_schema_extra=OPERATOR_SUPPLIED,
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


class SutConnectorBinding(ConnectorBinding):
    """The counter-party connector — an address the engine reaches, never manages.

    ADR-0019 §4 makes the two sides asymmetric: the engine operates its own
    connector through the management API, while the system under test is a
    deployment TestLab only talks to. An operator running a conformance test
    against someone else's connector has its DSP endpoint and its dataspace
    identity and nothing more, so the DSP endpoint is what decides this
    capability is bound. Demanding a management URL here would ask every
    operator for a credential the topology says they do not have.

    The management fields are inherited rather than removed because a SUT that
    *is* reachable — a local deployment an adopter runs both halves of — can
    still state them, and a step that provisions on the SUT side then has a
    service to talk to.
    """

    identity_field: ClassVar[str] = "dsp_url"

    dsp_url: str = Field(
        default="",
        description=(
            "DSP endpoint the engine negotiates against — the address of the connector under test."
        ),
        json_schema_extra=OPERATOR_SUPPLIED,
    )
    management_url: str = Field(
        default="",
        description=(
            "Management API URL, when the operator happens to run the SUT too. "
            "Left empty for a counter-party, which the engine only talks to."
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
        json_schema_extra=OPERATOR_SUPPLIED,
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
        json_schema_extra=OPERATOR_SUPPLIED,
    )

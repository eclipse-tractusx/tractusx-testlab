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

"""Where a step expects the system under test to call — the ``listener`` of the
``step_listening`` / ``step_waiting`` / ``step_received`` events.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field

#: EDC catalog filter keys (querySpec ``operandLeft``) for the offer's kind.
DCT_TYPE_FILTER_KEY = "'http://purl.org/dc/terms/type'.'@id'"
DCT_SUBJECT_FILTER_KEY = "'http://purl.org/dc/terms/subject'.'@id'"
VERSION_FILTER_KEY = "'https://w3id.org/catenax/ontology/common#version'"


class CatalogFilter(BaseModel):
    """One criterion of an EDC catalog request (``querySpec.filterExpression``)."""

    operandLeft: str
    operator: Literal["="] = "="
    operandRight: str


class ConnectorOffer(BaseModel):
    """The offer on the engine connector a call has to be negotiated for.

    What a counter-party needs to reach a mock that sits behind the engine
    connector: which connector to discover (``dsp_url``, ``participant_id``)
    and which offer to negotiate there.

    A system under test finds the offer by what it is — ``dct_type``,
    ``dct_subject``, ``version``, as ``catalog_filters`` spells them for an
    EDC catalog request — and not by ``asset_id``, which is the test's own
    name for the asset and usually carries the run's id.
    """

    asset_id: str
    dsp_url: str | None = None
    #: The connector's dataspace identity — a DID on a DCP dataspace, a BPNL
    #: on an older one.
    participant_id: str | None = None
    #: ``dct:type`` of the asset, e.g. ``https://w3id.org/catenax/taxonomy#CCMAPI``.
    dct_type: str | None = None
    #: ``dct:subject`` of the asset, when it has one.
    dct_subject: str | None = None
    #: ``cx-common:version`` of the asset, e.g. ``3.0``.
    version: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def catalog_filters(self) -> list[CatalogFilter]:
        """The catalog request that finds this offer: by type, subject and
        version when the step declared them, else by asset id."""
        found = [
            CatalogFilter(operandLeft=key, operandRight=value)
            for key, value in (
                (DCT_TYPE_FILTER_KEY, self.dct_type),
                (DCT_SUBJECT_FILTER_KEY, self.dct_subject),
                (VERSION_FILTER_KEY, self.version),
            )
            if value
        ]
        return found or [
            CatalogFilter(
                operandLeft="https://w3id.org/edc/v0.0.1/ns/id", operandRight=self.asset_id
            )
        ]


class BriefField(BaseModel):
    """One labelled value the person driving the system under test copies."""

    label: str = Field(min_length=1, description="What the value is, e.g. `header.receiverBpn`.")
    value: str | int | float | bool = Field(description="The value to copy.")


class WaitBrief(BaseModel):
    """What the test tells the person driving the system under test while it
    waits — written by the test author on the wait step (``with.brief``),
    in place of what a viewer would otherwise derive from the listener.

    Every part is optional: a viewer shows what is given and derives the rest.
    """

    message: str | None = Field(
        default=None, description="The note shown first: what is being asked, and why."
    )
    steps: list[str] = Field(
        default_factory=list, description="What to do, in order: one action per entry."
    )
    fields: list[BriefField] = Field(
        default_factory=list, description="Values to copy, shown beside the steps, in order."
    )


class Listener(BaseModel):
    """Where the system under test is expected to call.

    Published so that whoever is watching a run — or driving the SUT by hand —
    is told the one thing they need at that moment: which method, at which
    address. ``url`` is the address as the engine knows it; ``path`` is the
    part of it the mock server routes on.
    """

    method: str
    url: str
    path: str
    #: How the call has to arrive. ``direct``: the SUT calls ``url`` itself.
    #: ``dataplane``: the SUT reaches the mock only through the engine
    #: connector — it negotiates ``offer`` and calls through its data plane —
    #: so ``url`` is the data plane's target, never an address to hand the SUT.
    via: Literal["direct", "dataplane"] = "direct"
    #: The offer to negotiate, when ``via`` is ``dataplane``.
    offer: ConnectorOffer | None = None
    #: What the test tells the person driving the system under test, when the
    #: wait step gives a ``brief``.
    brief: WaitBrief | None = None

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The counter-party a DSP request is addressed to.

Its own module because a counter-party is a topology fact before it is a step
parameter: the address and the identity come from the SUT connector binding
unless a script names somebody else, so the mixin has to know about the
infrastructure the run was bound to, which the rest of the shared contract
models do not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from pydantic import Field

from tractusx_testlab.steps.step_contract import StepParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class CounterParty(NamedTuple):
    """The address and the identity a DSP request is addressed to."""

    address: str
    identity: str


class CounterPartyParams(StepParams):
    """The counter-party a DSP request is addressed to.

    Both fields fall back to the bound SUT connector, because in this topology
    the counter-party *is* the system under test: ADR-0019 binds
    ``infrastructure.sut.connector`` to the deployment the engine only talks to,
    and its ``dsp_url`` and ``participant_id`` are exactly that address and that
    identity. The operator already had to supply both for the binding to
    resolve, so a TCK that also declared them as ``env`` variables was asking
    for the same two values twice and letting them disagree.

    A script states them only when it addresses somebody the binding does not
    describe — a second provider, or an endpoint a discovery step resolved.
    """

    counter_party_address: str = Field(
        default="",
        description=(
            "DSP endpoint of the counter-party connector; defaults to the bound "
            "SUT connector's 'dsp_url'."
        ),
    )
    counter_party_id: str = Field(
        default="",
        description=(
            "Dataspace identity of the counter-party; defaults to the bound SUT "
            "connector's 'participant_id'."
        ),
    )

    def counter_party(self, context: StepContext) -> CounterParty:
        """The counter-party this step addresses, script first, binding second."""
        sut = context.infrastructure.sut.connector
        return CounterParty(
            address=self.counter_party_address or sut.dsp_url,
            identity=self.counter_party_id or sut.participant_id,
        )

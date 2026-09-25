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

from pydantic import BaseModel


class ConnectorOffer(BaseModel):
    """The offer on the engine connector a call has to be negotiated for.

    What a counter-party needs to reach a mock that sits behind the engine
    connector: which connector to discover (``dsp_url``, ``participant_id``)
    and which asset to negotiate there.
    """

    asset_id: str
    dsp_url: str | None = None
    #: The connector's dataspace identity — a DID on a DCP dataspace, a BPNL
    #: on an older one.
    participant_id: str | None = None


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

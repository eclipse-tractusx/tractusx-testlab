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

"""The DSP protocol version a request is made under, when a script picks one.

Which protocol a connector speaks follows from its dataspace release: a Saturn
connector speaks ``dataspace-protocol-http:2025-1`` and a Jupiter one speaks
``dataspace-protocol-http``.  A step therefore has no business asking for it —
the run is already bound to one connector service or the other, and that service
already knows.

What a *test* may legitimately want is to pin the protocol anyway: to prove a
provider rejects a version it does not support, or accepts one it does.  That is
what this mixin is for, and why the field defaults to empty rather than to a
protocol name.  Empty means "do not send one", which is what makes the release
decide — the SDK's consumer service carries the default for its own release, and
restating the mapping here would be a second copy of it, free to drift the first
time the SDK adds a release.
"""

from __future__ import annotations

from pydantic import Field

from tractusx_testlab.steps.step_contract import StepParams

__all__ = ["DspProtocolParams"]


class DspProtocolParams(StepParams):
    """Adds an optional DSP protocol override to a step's inputs."""

    protocol: str = Field(
        default="",
        description=(
            "DSP protocol version the request is made under, e.g. "
            "'dataspace-protocol-http:2025-1'. Left empty, the connector's "
            "dataspace version decides it."
        ),
    )

    def sdk_protocol(self) -> dict[str, str]:
        """The ``protocol`` keyword for an SDK call, or nothing when none was picked.

        Returned as a mapping to be splatted into the call rather than as a
        value, because "no protocol" has to reach the SDK as an *absent*
        argument.  Passing ``None`` or ``""`` would override the release default
        with a non-answer, which is the opposite of leaving it to the release.
        """
        return {"protocol": self.protocol} if self.protocol else {}

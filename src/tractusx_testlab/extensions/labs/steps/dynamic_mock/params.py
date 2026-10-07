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

"""Input contract of ``labs/mock/api/dynamic``. **Experimental.**"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.mock.api import MockRouteParams

#: The reply fields, read per call once the mock's steps have run.
REPLY_PARAMS = ("response_status", "response_body", "response_headers")

#: How long the mock's steps may take by default. The caller — usually a
#: connector's data plane forwarding the system under test's call — is
#: waiting on the reply the whole time, and gives up long before a minute.
DEFAULT_PROCESS_TIMEOUT_S = 10.0


class DynamicMockParams(MockRouteParams):
    """Input contract of ``labs/mock/api/dynamic``."""

    process: list[StepDefinition] = Field(
        default_factory=list,
        description=(
            "Steps run once for every call, in order, before the mock answers — the "
            "same shape as the steps nested in 'flow/if'. They read the call as "
            "'${{ *.request.body }}' (also headers, query, method and path, and any "
            "path into them, e.g. '${{ *.request.body.header.messageId }}'), and one "
            "another's outputs as '${{ *.process.<id>.<field> }}'. What they publish "
            "belongs to that call alone."
        ),
    )
    response_status: int | str = Field(
        default=200,
        description=(
            "Status code the mock answers with. Read per call, after 'process', so it "
            "may be a '${{ *.process.<id>.value }}' reference."
        ),
    )
    response_body: Any = Field(
        default_factory=dict,
        description=(
            "JSON body the mock answers with, read per call after 'process': one "
            "'${{ *.process.<id>.value }}' sends what a step built, or a structure "
            "with references inside it. Every '${{ }}' in it is read per call."
        ),
    )
    response_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Headers the mock answers with, read per call after 'process'.",
    )
    process_timeout: float = Field(
        default=DEFAULT_PROCESS_TIMEOUT_S,
        gt=0,
        description=(
            "Seconds 'process' may take for one call. The caller waits for the reply "
            "meanwhile; past this the mock answers 500."
        ),
    )

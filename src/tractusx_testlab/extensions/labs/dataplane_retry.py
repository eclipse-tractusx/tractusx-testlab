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

"""``retry_on`` — retry a data-plane call while it answers a listed status. **Experimental.**

A ``labs`` parameter extension on ``connector/dataplane/http_request``. A
provider that publishes an asset before its backend is ready answers the first
pulls with a 404 or a 503; a test that has to reach the ready state otherwise
needs a ``flow/retry`` around the call, which retries on *any* failure and hides
the one it was not meant to tolerate. This retries on the statuses the test
names and nothing else::

    - uses: connector/dataplane/http_request
      with:
        path: /certificates/42
        retry_on: [404, 503]
        retry_attempts: 5
        retry_delay_s: 2

Every attempt is a real call: each one is published as its own
``tck.test.step.call`` event, and the step's output is the last answer. A
transport error is not a status and is not retried.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.steps.step_extension import ExtensionParams, StepExtension, extends

if TYPE_CHECKING:
    from tractusx_testlab.models import StepDefinition
    from tractusx_testlab.player.execution.context import StepContext
    from tractusx_testlab.steps.step_contract import StepOutput
    from tractusx_testlab.steps.step_extension import Proceed

logger = logging.getLogger(__name__)


class DataplaneRetryParams(ExtensionParams):
    """Retry the call while the data plane answers with one of ``retry_on``."""

    retry_on: list[int] = Field(
        min_length=1,
        description="Status codes that make the call run again, e.g. [404, 503].",
    )
    retry_attempts: int = Field(
        default=3, ge=2, le=10, description="Calls in total, the first one included."
    )
    retry_delay_s: float = Field(
        default=1.0, ge=0, le=60, description="Seconds to wait between two calls."
    )


@extends("connector/dataplane/http_request", extension="labs")
class DataplaneRetry(StepExtension[DataplaneRetryParams]):
    """Run the call again while its status is one the test listed."""

    params_model = DataplaneRetryParams

    async def around(
        self,
        params: DataplaneRetryParams,
        context: StepContext,
        definition: StepDefinition,
        proceed: Proceed,
    ) -> StepOutput[Any]:
        for attempt in range(1, params.retry_attempts):
            output = await proceed()
            status = output.response.status_code if output.response is not None else None
            if status not in params.retry_on:
                return output
            logger.info(
                "retry_on: attempt %d of %d answered %s, calling again in %ss",
                attempt,
                params.retry_attempts,
                status,
                params.retry_delay_s,
            )
            await asyncio.sleep(params.retry_delay_s)
        return await proceed()

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

"""``labs/util/now`` — the current time. **Experimental.**"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams, StepValue

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext


class NowParams(StepParams):
    """Input contract of ``labs/util/now`` — the step takes nothing."""


class NowOutput(StepValue[str]):
    """The time the step ran, in UTC, as ISO 8601 with milliseconds: ``2026-09-27T20:44:49.995Z``."""


@step("labs/util/now")
class NowStep(BaseStep[NowParams, NowOutput]):
    """Read the current time, in UTC.

    For a message a test builds that has to say when it was sent — a
    ``sentDateTime`` in a notification header, or in a mock's reply built by
    ``labs/mock/api/dynamic``. Time zone aware, with a ``Z`` suffix, which is
    what JSON schemas mean by ``format: date-time``.
    """

    params_model = NowParams
    output_model = NowOutput

    async def execute(
        self,
        params: NowParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[NowOutput]:
        stamp = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return StepOutput(value=NowOutput(stamp))

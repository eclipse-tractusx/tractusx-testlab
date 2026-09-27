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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""``labs/util/now`` — the current time, as a message header wants it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.extensions.labs.steps.now import NowParams, NowStep
from tractusx_testlab.models import StepDefinition

pytestmark = pytest.mark.asyncio


async def _now() -> str:
    output = await NowStep().execute(NowParams(), MagicMock(), StepDefinition(uses="labs/util/now"))
    return str(output.value.root)


async def test_it_is_utc_with_a_z_and_milliseconds() -> None:
    stamp = await _now()

    assert stamp.endswith("Z")
    assert len(stamp.split(".")[1]) == len("123Z")


async def test_it_is_the_time_the_step_ran() -> None:
    stamp = await _now()

    ran_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert abs(datetime.now(UTC) - ran_at) < timedelta(seconds=5)

#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################

"""Tests for flow/delay."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.flow.delay import DelayStep


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinitionV2:
    return StepDefinitionV2(id="wait", uses="flow/delay")


class TestDelayStep:
    @pytest.mark.asyncio
    async def test_waits_at_least_the_configured_duration(self, context: StepContext) -> None:
        started = time.monotonic()
        await DelayStep().invoke({"seconds": 0.05}, context, _definition())
        assert time.monotonic() - started >= 0.05

    @pytest.mark.asyncio
    async def test_defaults_to_one_second_param(self, context: StepContext) -> None:
        # Not awaiting a full second here — just confirm the default doesn't raise.
        output = await DelayStep().invoke({"seconds": 0}, context, _definition())
        assert output.value is None

    @pytest.mark.asyncio
    async def test_rejects_negative_duration(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="seconds: Input should be greater than or equal to 0"):
            await DelayStep().invoke({"seconds": -1}, context, _definition())

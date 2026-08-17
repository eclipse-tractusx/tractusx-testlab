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

"""Tests for the flow/retry step — retries a nested list of steps until they pass."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.flow.retry import RetryStep
from tractusx_testlab.steps.utility.log import LogStep


def _context() -> MagicMock:
    return MagicMock()


def _step_def(**kwargs) -> StepDefinition:
    return StepDefinition(id="s", uses="flow/retry", **kwargs)


class TestRetryStep:
    @pytest.mark.asyncio
    async def test_requires_steps_param(self) -> None:
        with pytest.raises(ValueError):
            await RetryStep().invoke({}, _context(), _step_def())

    @pytest.mark.asyncio
    async def test_rejects_empty_steps_list(self) -> None:
        with pytest.raises(ValueError):
            await RetryStep().invoke({"steps": []}, _context(), _step_def())

    @pytest.mark.asyncio
    async def test_immediate_success_runs_once(self) -> None:
        params = {"steps": [{"uses": "util/log", "with": {"message": "hi"}}]}

        output = await RetryStep().invoke(params, _context(), _step_def())

        assert output.value == [None]

    @pytest.mark.asyncio
    async def test_retries_until_success(self, monkeypatch) -> None:
        call_count = {"n": 0}
        original = LogStep.execute

        async def sometimes_fails(self, p, context, definition):
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise ValueError("transient failure")
            return await original(self, p, context, definition)

        monkeypatch.setattr(LogStep, "execute", sometimes_fails)
        params = {
            "steps": [{"uses": "util/log", "with": {"message": "hi"}}],
            "max_attempts": 3,
            "delay_s": 0,
        }

        output = await RetryStep().invoke(params, _context(), _step_def())

        assert call_count["n"] == 2
        assert output.value == [None]

    @pytest.mark.asyncio
    async def test_stops_after_max_attempts_still_failing(self, monkeypatch) -> None:
        async def always_fails(self, p, context, definition):
            raise ValueError("boom")

        monkeypatch.setattr(LogStep, "execute", always_fails)
        params = {
            "steps": [{"uses": "util/log", "with": {"message": "hi"}}],
            "max_attempts": 2,
            "delay_s": 0,
        }

        with pytest.raises(RuntimeError):
            await RetryStep().invoke(params, _context(), _step_def())

    @pytest.mark.asyncio
    async def test_unknown_nested_step_type_fails(self) -> None:
        params = {"steps": [{"uses": "does/not_exist"}], "max_attempts": 1}

        with pytest.raises(RuntimeError):
            await RetryStep().invoke(params, _context(), _step_def())

    @pytest.mark.asyncio
    async def test_recursive_nested_retry(self) -> None:
        """A flow/retry step may itself appear inside another flow/retry's steps list."""
        params = {
            "steps": [
                {
                    "uses": "flow/retry",
                    "with": {
                        "steps": [{"uses": "util/log", "with": {"message": "hi"}}],
                        "max_attempts": 1,
                    },
                },
            ],
            "max_attempts": 1,
        }

        output = await RetryStep().invoke(params, _context(), _step_def())

        assert output.value == [[None]]

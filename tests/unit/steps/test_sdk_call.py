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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""No SDK call may run forever.

The SDK issues every request through ``requests`` with no timeout, and its poll
loops add to their elapsed time only once a call has returned — so ``max_wait``
never fires on a query that is still hanging, and a negotiation that was not
working consumed the whole CI job instead of failing. Every call the engine
dispatches to the SDK now carries a deadline, and reaching it fails the step
with the operation and the seconds waited in the message.
"""

from __future__ import annotations

import threading

import pytest

from tractusx_testlab.models import StepExecutionError
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.shared_models import DEFAULT_MAX_WAIT, dsp_budget


def _answer(value: str = "transfer-1") -> str:
    """A blocking SDK call that returns straight away."""
    return value


class TestBoundedSdkCalls:
    async def test_a_call_that_answers_returns_its_value(self) -> None:
        assert await sdk_call.run(_answer) == "transfer-1"

    async def test_arguments_reach_the_operation(self) -> None:
        assert await sdk_call.run(_answer, value="edr-9") == "edr-9"

    async def test_a_call_that_never_answers_fails_the_step(self) -> None:
        release = threading.Event()
        try:
            with pytest.raises(StepExecutionError) as raised:
                await sdk_call.run_within(0.05, release.wait)
        finally:
            release.set()

        assert "did not answer within 0.05s" in str(raised.value)

    async def test_the_failure_names_the_operation_that_hung(self) -> None:
        release = threading.Event()
        try:
            with pytest.raises(StepExecutionError) as raised:
                await sdk_call.run_within(0.05, release.wait)
        finally:
            release.set()

        assert "sdk/Event.wait" in str(raised.value)

    def test_the_default_bound_is_finite(self) -> None:
        """The point of the bound is that there is one — an unset one is the bug."""
        assert 0 < sdk_call.DEFAULT_SDK_TIMEOUT < float("inf")


class TestDspBudget:
    def test_the_budget_covers_both_of_the_sdks_waits(self) -> None:
        """Negotiation, then EDR entry — each up to ``max_wait`` — plus a catalog call."""
        assert dsp_budget(30) == 2 * 30 + sdk_call.DEFAULT_SDK_TIMEOUT

    def test_a_step_that_waits_longer_is_given_longer(self) -> None:
        assert dsp_budget(DEFAULT_MAX_WAIT * 2) > dsp_budget(DEFAULT_MAX_WAIT)

    def test_the_budget_exceeds_the_wait_it_is_derived_from(self) -> None:
        """A flow that is merely slow must still finish inside its own budget."""
        assert dsp_budget(DEFAULT_MAX_WAIT) > DEFAULT_MAX_WAIT

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

"""The runner records what a step sent, whether or not the step co-operates.

`ADR-0016 <../../../docs/developer/decision-records/backend/ADR-0016-execution-trace-format.md>`_
puts the wire on the step event, and the point of recording it in the runner
rather than in the steps is the step that never gets to describe its own call.
These run a real step through the real runner to check that the promise holds
from both ends: the step that returned, and the step that raised.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from tractusx_testlab.logging import wire
from tractusx_testlab.models.authoring.definitions import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.steps.http.request import HttpRequestStep

URL = "https://api.example.test/parts"


def _definition() -> StepDefinition:
    return StepDefinition(uses="http/http_request", name="call the backend", with_={"url": URL})


def _answer(status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        json={"ok": True},
        request=httpx.Request("GET", URL),
    )


class TestStepExchanges:
    async def test_a_step_reports_the_call_it_made(self, mock_context: MagicMock) -> None:
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=_answer()
        ):
            result = await run_step(
                HttpRequestStep,
                _definition(),
                "call_backend",
                mock_context,
            )

        assert result.status == StepStatus.PASSED
        [item] = result.exchanges
        assert item.request.url == URL
        assert item.context == wire.ENGINE_CONTEXT
        assert item.response is not None
        assert item.response.status_code == 200

    async def test_a_call_is_published_while_the_step_is_still_running(
        self, mock_context: MagicMock
    ) -> None:
        """The point of reporting: a minute-long step is watchable, not a spinner."""
        published: list[tuple[str, str | None, int, str]] = []
        mock_context.report_call = lambda step_type, step_id, index, call: published.append(
            (step_type, step_id, index, call.request.url)
        )

        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=_answer()
        ):
            await run_step(HttpRequestStep, _definition(), "call_backend", mock_context)

        assert published == [("http/http_request", None, 1, URL)]

    async def test_a_step_reports_what_it_was_given(self, mock_context: MagicMock) -> None:
        """``inputs`` is the ``with:`` block once every reference resolved."""
        with patch.object(
            httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=_answer()
        ):
            result = await run_step(HttpRequestStep, _definition(), "call_backend", mock_context)

        assert result.inputs is not None
        assert result.inputs["url"] == URL

    async def test_a_step_that_raised_reports_the_call_that_failed(
        self, mock_context: MagicMock
    ) -> None:
        """The case the recorder exists for: nothing else describes the request."""
        with patch.object(
            httpx.AsyncClient,
            "request",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            result = await run_step(
                HttpRequestStep,
                _definition(),
                "call_backend",
                mock_context,
            )

        assert result.status == StepStatus.FAILED
        # The step never reached the line that names its subject, so the runner
        # fills it from the call that failed.
        assert result.request is not None
        assert result.request.url == URL
        assert result.response is None
        assert result.exchanges[0].error == "ConnectTimeout: timed out"

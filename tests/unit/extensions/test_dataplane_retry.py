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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.


"""``retry_on`` — the ``labs`` parameter extension on ``connector/dataplane/http_request``.

Run through the real runner with the HTTP client patched, so what is counted is
calls the step really made. The live counterpart is
``tests/e2e/connector-dtr-smoke/tests/experimental_extensions.yaml``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from tractusx_testlab.authoring.step_docs import render_step
from tractusx_testlab.models.authoring.definitions import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.steps.connector.dataplane import DataplaneCallStep
from tractusx_testlab.steps.step_extension import extensions_for

URL = "https://dataplane.example.test/public"


def _answer(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status, json=body or {"status": status}, request=httpx.Request("GET", URL)
    )


def _fetch(**retry: object) -> StepDefinition:
    return StepDefinition(
        id="fetch",
        uses="connector/dataplane/http_request",
        with_={"dataplane_url": URL, "edr_token": "token", "retry_delay_s": 0, **retry},
    )


async def _run(definition: StepDefinition, context: MagicMock, *answers: httpx.Response):
    client = AsyncMock(side_effect=list(answers))
    with patch.object(httpx.AsyncClient, "request", client):
        result = await run_step(DataplaneCallStep, definition, "fetch", context)
    return result, client.await_count


class TestRetrying:
    async def test_a_listed_status_calls_again_until_it_is_not(self, mock_context) -> None:
        result, calls = await _run(
            _fetch(retry_on=[503], retry_attempts=5),
            mock_context,
            _answer(503),
            _answer(503),
            _answer(200, {"ready": True}),
        )
        assert result.status is StepStatus.PASSED, result.error
        assert calls == 3
        assert result.output == {"ready": True}
        assert result.response.status_code == 200

    async def test_a_status_not_listed_is_returned_at_once(self, mock_context) -> None:
        result, calls = await _run(_fetch(retry_on=[503]), mock_context, _answer(404))
        assert calls == 1
        assert result.response.status_code == 404

    async def test_the_attempts_bound_the_calls_and_the_last_answer_stands(
        self, mock_context
    ) -> None:
        result, calls = await _run(
            _fetch(retry_on=[503], retry_attempts=2), mock_context, _answer(503), _answer(503)
        )
        assert calls == 2
        assert result.response.status_code == 503

    async def test_every_attempt_is_recorded_as_its_own_call(self, mock_context) -> None:
        result, _ = await _run(
            _fetch(retry_on=[200], retry_attempts=2), mock_context, _answer(200), _answer(200)
        )
        assert len(result.exchanges) == 2

    async def test_without_the_keys_the_step_calls_once(self, mock_context) -> None:
        definition = StepDefinition(
            id="fetch",
            uses="connector/dataplane/http_request",
            with_={"dataplane_url": URL, "edr_token": "token"},
        )
        result, calls = await _run(definition, mock_context, _answer(503))
        assert calls == 1
        assert result.status is StepStatus.PASSED


class TestItsParameters:
    async def test_attempts_without_statuses_fail_the_step_in_the_extensions_name(
        self, mock_context
    ) -> None:
        result, calls = await _run(_fetch(retry_attempts=3), mock_context, _answer(200))
        assert result.status is StepStatus.FAILED
        assert "experimental extension 'labs'" in result.error
        assert "retry_on" in result.error
        assert calls == 0

    async def test_a_single_attempt_is_refused(self, mock_context) -> None:
        result, _ = await _run(_fetch(retry_on=[503], retry_attempts=1), mock_context)
        assert result.status is StepStatus.FAILED


class TestRegistration:
    def test_it_is_registered_on_the_data_plane_step_under_labs(self) -> None:
        (extension,) = extensions_for("connector/dataplane/http_request")
        assert extension.extension == "labs"
        assert extension.param_keys() == {"retry_on", "retry_attempts", "retry_delay_s"}

    def test_the_step_reference_lists_it_as_experimental(self) -> None:
        page = "\n".join(render_step(DataplaneCallStep))
        assert "**Experimental inputs** — extension `labs`" in page
        assert "| `retry_on` |" in page

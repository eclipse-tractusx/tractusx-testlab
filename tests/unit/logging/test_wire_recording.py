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

"""What a step reports about the calls it made.

The case these exist for is the failing one. A step that raises never reaches
the line that would have described its request, so before the recorder a 403
three calls into a DSP flow left nothing behind but the exception text — which
is what made a real run undebuggable.

The calls are recorded by the SDK's tracer, at the same ``trace_call`` seam the
SDK instruments its own adapters with. A test therefore records through
``trace_call`` where it stands in for the SDK, and through ``http_client`` where
the engine is the one calling.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from tractusx_sdk.dataspace.tools import trace_call

from tractusx_testlab.logging import wire
from tractusx_testlab.models.runtime.results import (
    HttpExchange,
    HttpRequest,
    HttpResponse,
    StepResult,
)
from tractusx_testlab.steps import http_client

#: What the SDK's context looks like: the method that performed the call.
SDK_CONTEXT = "CatalogController.get_catalog"


def _sdk_call(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any = None,
    answer: httpx.Response | None = None,
) -> None:
    """Record one call the way the SDK records the ones it makes."""
    with trace_call(method, url, headers=headers, body=body, context=SDK_CONTEXT) as call:
        call.set_response(answer if answer is not None else _answer())


def _answer(
    status: int = 200, body: Any = None, headers: dict[str, str] | None = None
) -> httpx.Response:
    """A response the tracer can read, as the transports hand one over."""
    return httpx.Response(
        status,
        json=body if body is not None else {"ok": True},
        headers=headers,
        request=httpx.Request("GET", "https://sut/"),
    )


class TestRecording:
    def test_calls_outside_a_step_are_not_recorded(self) -> None:
        with trace_call("GET", "https://x") as call:
            assert not call.enabled

    def test_a_step_collects_its_calls_in_order(self) -> None:
        with wire.recording("catalog") as recorder:
            for n in range(3):
                _sdk_call(f"https://x/{n}")
        assert [item.request.url for item in recorder.exchanges] == [
            "https://x/0",
            "https://x/1",
            "https://x/2",
        ]

    def test_a_nested_step_does_not_bleed_into_its_parent(self) -> None:
        """Each step reports its own calls — a flow step does not inherit them."""
        with wire.recording("retry") as outer:
            _sdk_call("https://outer")
            with wire.recording("negotiate") as inner:
                _sdk_call("https://inner")
        assert [item.request.url for item in outer.exchanges] == ["https://outer"]
        assert [item.request.url for item in inner.exchanges] == ["https://inner"]

    def test_a_call_names_the_method_that_made_it(self) -> None:
        """Which layer sent it is the first question asked of a failing call."""
        with wire.recording("catalog") as recorder:
            _sdk_call("https://sut/catalog/request", method="POST")
        assert recorder.exchanges[0].context == SDK_CONTEXT

    async def test_the_engines_own_calls_are_recorded_too(self) -> None:
        """One list, both transports: httpx here, the SDK's requests above."""
        with wire.recording("http_request") as recorder:
            with patch.object(
                httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=_answer()
            ):
                await http_client.request("GET", "https://api/parts", params={"page": "1"})

        [item] = recorder.exchanges
        assert item.context == wire.ENGINE_CONTEXT
        assert item.request.params == {"page": "1"}
        assert item.response is not None
        assert item.response.status_code == 200

    async def test_a_call_that_raised_keeps_its_request_and_the_error(self) -> None:
        """The refused connection is the evidence, so it is not lost with it."""
        with wire.recording("http_request") as recorder:
            with patch.object(
                httpx.AsyncClient,
                "request",
                new_callable=AsyncMock,
                side_effect=httpx.ConnectTimeout("timed out"),
            ):
                with pytest.raises(httpx.ConnectTimeout):
                    await http_client.request("GET", "https://unreachable")

        [item] = recorder.exchanges
        assert item.request.url == "https://unreachable"
        assert item.response is None
        assert item.error == "ConnectTimeout: timed out"


class TestReportingWhileItHappens:
    """A call is handed over when it comes back, not when the step is over."""

    def test_each_call_is_reported_as_it_finishes(self) -> None:
        reported: list[str] = []
        with wire.recording("catalog", on_call=lambda call: reported.append(call.request.url)):
            _sdk_call("https://x/0")
            # Reported inside the block: the step has not finished, and the
            # point of reporting is that somebody is watching it run.
            assert reported == ["https://x/0"]
            _sdk_call("https://x/1")
        assert reported == ["https://x/0", "https://x/1"]

    def test_a_failed_call_is_reported_too(self) -> None:
        reported: list[HttpExchange] = []
        with wire.recording("catalog", on_call=reported.append):
            with pytest.raises(RuntimeError), trace_call("GET", "https://unreachable"):
                raise RuntimeError("connection refused")
        [call] = reported
        assert call.error == "RuntimeError: connection refused"
        assert call.response is None

    def test_a_nested_step_reports_to_its_own_watcher(self) -> None:
        """The SDK finishes an entry on the outermost tracer; the call is still the child's."""
        outer: list[str] = []
        inner: list[str] = []
        with wire.recording("retry", on_call=lambda call: outer.append(call.request.url)):
            _sdk_call("https://outer")
            with wire.recording("negotiate", on_call=lambda call: inner.append(call.request.url)):
                _sdk_call("https://inner")
        assert outer == ["https://outer"]
        assert inner == ["https://inner"]

    def test_a_run_nobody_is_watching_still_records(self) -> None:
        with wire.recording("catalog") as recorder:
            _sdk_call("https://x/0")
        assert len(recorder.exchanges) == 1


class TestAttaching:
    def test_a_step_that_raised_still_reports_what_it_sent(self) -> None:
        """The whole point: a failure keeps the call that failed."""
        with wire.recording("catalog") as recorder:
            _sdk_call("https://sut/catalog", method="POST", answer=_answer(403))
        result = StepResult(step_name="s", step_type="x")
        wire.attach_to(result, recorder)

        assert result.request is not None
        assert result.request.url == "https://sut/catalog"
        assert result.response is not None
        assert result.response.status_code == 403

    def test_the_step_keeps_the_exchange_it_chose(self) -> None:
        """A step that named its subject knows which call the script is about."""
        with wire.recording("catalog") as recorder:
            _sdk_call("https://incidental")
        result = StepResult(
            step_name="s",
            step_type="x",
            request=HttpRequest(method="POST", url="https://the-point"),
            response=HttpResponse(status_code=200),
        )
        wire.attach_to(result, recorder)

        assert result.request.url == "https://the-point"
        assert len(result.exchanges) == 1

    def test_a_step_that_made_no_call_reports_none(self) -> None:
        with wire.recording("base64") as recorder:
            pass
        result = StepResult(step_name="s", step_type="util/base64")
        wire.attach_to(result, recorder)

        assert result.exchanges == []
        assert result.request is None


class TestRedaction:
    def test_credentials_never_reach_the_trace(self) -> None:
        """By header name, not by value shape: guessing at shapes leaks tokens."""
        with wire.recording("catalog") as recorder:
            _sdk_call(
                "https://sut/catalog",
                headers={
                    "Authorization": "Bearer super-secret",
                    "X-Api-Key": "key-123",
                    "Cookie": "session=abc",
                    "Content-Type": "application/json",
                },
            )

        sent = recorder.exchanges[0].request.headers or {}
        assert sent["Authorization"] == "***"
        assert sent["X-Api-Key"] == "***"
        assert sent["Cookie"] == "***"
        assert sent["Content-Type"] == "application/json"

    def test_a_json_body_is_stored_as_json_not_as_a_string(self) -> None:
        """The SDK sends its models as JSON strings; a trace is navigated as JSON."""
        with wire.recording("catalog") as recorder:
            _sdk_call("https://sut/catalog", method="POST", body='{"@type": "CatalogRequest"}')
        assert recorder.exchanges[0].request.body == {"@type": "CatalogRequest"}

    def test_a_non_json_body_is_kept_as_the_sut_sent_it(self) -> None:
        with wire.recording("catalog") as recorder:
            _sdk_call(
                "https://sut/catalog",
                answer=httpx.Response(
                    403,
                    text="<html>403</html>",
                    request=httpx.Request("GET", "https://sut/catalog"),
                ),
            )
        assert recorder.exchanges[0].response.body == "<html>403</html>"

    def test_a_huge_body_is_clipped_with_the_cut_made_visible(self) -> None:
        with wire.recording("pull") as recorder:
            _sdk_call("https://sut/data", method="POST", body="x" * 30_000)

        clipped = recorder.exchanges[0].request.body
        assert "truncated" in clipped
        assert len(clipped) < 30_000

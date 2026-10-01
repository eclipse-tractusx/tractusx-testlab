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

"""Credentials are taken out of what a run writes down by the name they are filed under."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from tractusx_sdk.dataspace.tools import trace_call

from tractusx_testlab.logging import wire
from tractusx_testlab.logging.masking import forget_secrets, register_secret
from tractusx_testlab.logging.wire.redaction import forget_secret_headers
from tractusx_testlab.models import StepStatus
from tractusx_testlab.models.runtime.results import (
    HttpExchange,
    HttpRequest,
    HttpResponse,
    StepResult,
)
from tractusx_testlab.player.execution.monitor import ExecutionMonitor

_TOKEN = "eyJhbGciOiJSUzI1NiJ9.edr-token-value"
_SECRET = "client-secret-value-0123"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    forget_secret_headers()
    yield
    forget_secrets()
    forget_secret_headers()


def _record(url: str, *, body: Any = None, answer: Any = None, headers: Any = None) -> Any:
    with wire.recording("step") as recorder:
        with trace_call("POST", url, headers=headers, body=body, context="sdk") as call:
            call.set_response(
                httpx.Response(200, json=answer or {}, request=httpx.Request("POST", url))
            )
    return recorder.exchanges[0]


class TestByKey:
    def test_json_documents_are_redacted_at_any_depth(self) -> None:
        redacted = wire.redact_secrets(
            {
                "endpoint": "https://dp/public",
                "authorization": _TOKEN,
                "nested": [{"refreshToken": _TOKEN, "expiresIn": "300"}],
                "https://w3id.org/edc/v0.0.1/ns/authorization": _TOKEN,
                "tx-auth:refreshToken": _TOKEN,
                "header:X-Api-Key": _TOKEN,
                "client_secret": _SECRET,
                "access_token": _TOKEN,
                "empty_password": "",
            }
        )
        assert _TOKEN not in str(redacted)
        assert _SECRET not in str(redacted)
        assert redacted["endpoint"] == "https://dp/public"
        assert redacted["nested"][0]["expiresIn"] == "300"

    def test_a_form_body_is_redacted_and_kept_a_form(self) -> None:
        form = f"grant_type=password&username=alice&password=pw&client_secret={_SECRET}"
        assert wire.redact_secrets(form) == (
            "grant_type=password&username=alice&password=***&client_secret=***"
        )

    def test_text_that_is_not_a_form_is_left_alone(self) -> None:
        assert wire.redact_secrets("token expired, try again") == "token expired, try again"

    def test_a_registered_header_name_is_redacted_everywhere_from_then_on(self) -> None:
        assert wire.safe_headers({"X-EDC-Key": "k"}) == {"X-EDC-Key": "k"}
        wire.register_secret_header("X-EDC-Key")
        assert wire.safe_headers({"x-edc-key": "k"}) == {"x-edc-key": "***"}
        assert wire.redact_secrets({"header:X-EDC-Key": "k"}) == {"header:X-EDC-Key": "***"}

    def test_a_registered_header_is_redacted_by_the_tracer(self) -> None:
        wire.register_secret_header("X-EDC-Key")
        exchange = _record("https://cp/management/v3/assets", headers={"X-EDC-Key": "short"})
        assert exchange.request.headers["X-EDC-Key"] == "***"


class TestRecordedCalls:
    def test_an_edr_data_address_response_is_redacted_the_moment_it_is_recorded(self) -> None:
        exchange = _record(
            "https://cp/management/v3/edrs/t-1/dataaddress",
            answer={"endpoint": "https://dp/public", "authorization": _TOKEN},
        )
        assert exchange.response.body == {"endpoint": "https://dp/public", "authorization": "***"}

    def test_a_token_request_form_is_redacted_in_the_recorded_call(self) -> None:
        exchange = _record(
            "https://idp/token",
            body={"grant_type": "client_credentials", "client_secret": _SECRET},
            answer={"access_token": _TOKEN, "token_type": "Bearer"},
        )
        assert exchange.request.body == {"grant_type": "client_credentials", "client_secret": "***"}
        assert exchange.response.body == {"access_token": "***", "token_type": "Bearer"}


def _result(**update: Any) -> StepResult:
    return StepResult(
        step_name="s", step_type="http/http_request", status=StepStatus.PASSED, **update
    )


class TestAsRecorded:
    def test_the_recorded_call_never_undoes_a_step_s_own_redaction(self) -> None:
        raw = HttpExchange(
            request=HttpRequest(
                method="POST", url="https://idp/token", body={"client_secret": _SECRET}
            ),
            response=HttpResponse(status_code=200, body={"refresh_token": _TOKEN}),
        )
        result = _result(
            request=HttpRequest(
                method="POST", url="https://idp/token", body={"client_secret": "***"}
            ),
            exchanges=[raw],
        )

        record = wire.as_recorded(result)

        assert record.request.body == {"client_secret": "***"}
        assert record.response.body == {"refresh_token": "***"}
        assert record.exchanges[0].request.body == {"client_secret": "***"}
        # What the run keeps is untouched.
        assert result.exchanges[0].request.body == {"client_secret": _SECRET}

    def test_resolved_inputs_are_redacted_by_key(self) -> None:
        result = _result(inputs={"client_secret": "short", "headers": {"Authorization": "x"}})
        record = wire.as_recorded(result)
        assert record.inputs == {"client_secret": "***", "headers": {"Authorization": "***"}}


class TestMonitor:
    def test_step_started_inputs_are_redacted_by_key(self) -> None:
        received: list[dict[str, Any]] = []
        monitor = ExecutionMonitor(MagicMock())
        monitor.add_callback(lambda _event, payload: received.append(payload))

        monitor.on_step_started(
            "job",
            "test",
            "s",
            0,
            "security/oauth2/password",
            "s",
            inputs={"username": "alice", "password": "pw"},
        )

        assert received[0]["inputs"] == {"username": "alice", "password": "***"}

    def test_a_registered_value_is_masked_in_an_error_line(self) -> None:
        register_secret(_TOKEN)
        received: list[dict[str, Any]] = []
        monitor = ExecutionMonitor(MagicMock())
        monitor.add_callback(lambda _event, payload: received.append(payload))

        monitor._emit("step.failed", error=f"401 for token {_TOKEN}")

        assert received == [{"error": "401 for token ***"}]

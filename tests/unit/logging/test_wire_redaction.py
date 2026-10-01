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
        # A name that says nothing about a credential, so only registering it counts.
        assert wire.safe_headers({"X-Sut-Pass": "k"}) == {"X-Sut-Pass": "k"}
        wire.register_secret_header("X-Sut-Pass")
        assert wire.safe_headers({"x-sut-pass": "k"}) == {"x-sut-pass": "***"}
        assert wire.redact_secrets({"header:X-Sut-Pass": "k"}) == {"header:X-Sut-Pass": "***"}

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


class TestSecretNames:
    """A credential is known by what its name contains, not by an exact list."""

    @pytest.mark.parametrize(
        "name",
        [
            "client_assertion",
            "assertion",
            "subject_token",
            "actor_token",
            "code_verifier",
            "jwt",
            "private_key",
            "privateKey",
            "passwd",
            "pwd",
            "credentials",
            "x-vault-token",
            "x-amz-security-token",
            "Ocp-Apim-Subscription-Key",
            "sut_password",
            "bearerToken",
            "edc_api_key",
            "dtr-api-key",
            "tx-auth:refreshToken",
            "infrastructure.sut.connector.api_key",
        ],
    )
    def test_a_credential_name_is_secret(self, name: str) -> None:
        assert wire.is_secret_key(name)

    @pytest.mark.parametrize(
        "name",
        [
            "token_type",
            "tokenUrl",
            "token_url",
            "token_endpoint",
            "expires_in",
            "api_key_header",
            "has_secret",
            "isToken",
            "require_api_key",
            "secret_id",
            "credential_url",
            "refresh_endpoint",
            "tx-auth:refreshEndpoint",
            "subject_token_type",
            "client_id",
            "code",
            "assertions",
            "assertion_summary",
            "content-type",
        ],
    )
    def test_a_name_about_a_credential_is_not(self, name: str) -> None:
        assert not wire.is_secret_key(name)

    @pytest.mark.parametrize(
        "header", ["X-Forwarded-Access-Token", "X-Session-Id", "Cookie", "X-Custom-Auth"]
    )
    def test_a_header_naming_a_credential_is_redacted(self, header: str) -> None:
        assert wire.safe_headers({header: "v"}) == {header: "***"}

    @pytest.mark.parametrize(
        "header", ["Content-Type", "Accept", "X-Request-Id", "WWW-Authenticate"]
    )
    def test_a_harmless_header_is_kept(self, header: str) -> None:
        assert wire.safe_headers({header: "v"}) == {header: "v"}

    def test_a_flag_under_a_credential_name_is_kept(self) -> None:
        assert wire.redact_secrets({"secret": True, "password": False}) == {
            "secret": True,
            "password": False,
        }

    def test_an_assertion_is_a_credential_only_as_text(self) -> None:
        check = {"uses": "assert/equals", "with": {"input": "status_code"}}
        assert wire.redact_secrets({"assertion": "eyJ.jwt.sig"}) == {"assertion": "***"}
        assert wire.redact_secrets({"assertion": check}) == {"assertion": check}


class TestUrls:
    """A credential in a URL's query is redacted; the URL is otherwise as written."""

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://h/p?api_key=SECRET1", "https://h/p?api_key=***"),
            ("https://h/p?x=1&access_token=SECRET1#f", "https://h/p?x=1&access_token=***#f"),
            ("https://h/p?token=SECRET1&sig=abc", "https://h/p?token=***&sig=abc"),
            ("https://alice:pw@h/p", "https://alice:***@h/p"),
            ("https://h/p?q=a%20b&page=2", "https://h/p?q=a%20b&page=2"),
            ("https://h/p", "https://h/p"),
        ],
    )
    def test_a_credential_named_parameter_is_redacted(self, url: str, expected: str) -> None:
        assert wire.redact_url(url) == expected

    def test_a_url_inside_a_document_is_redacted(self) -> None:
        body = {"callbackAddress": "https://h/cb?token=SECRET1"}
        assert wire.redact_secrets(body) == {"callbackAddress": "https://h/cb?token=***"}

    def test_a_registered_value_is_masked_percent_encoded(self) -> None:
        register_secret("p@ss w0rd/42!x", explicit=True)
        assert wire.written("https://h/p?k=p%40ss+w0rd%2F42%21x") == "https://h/p?k=***"

    def test_the_recorded_call_redacts_its_url_and_its_headers(self) -> None:
        exchange = _record(
            "https://h/p?access_token=SECRET1",
            headers={"X-Forwarded-Access-Token": "SECRET2", "Content-Type": "application/json"},
        )
        assert exchange.request.url == "https://h/p?access_token=***"
        assert exchange.request.headers == {
            "X-Forwarded-Access-Token": "***",
            "Content-Type": "application/json",
        }


def _check(field: str, *, expected: Any, actual: Any) -> Any:
    from tractusx_testlab.models import Assertion
    from tractusx_testlab.models.runtime.results import AssertionResult

    return AssertionResult(
        assertion=Assertion.model_validate({"uses": "assert/equals", "with": {"input": field}}),
        passed=False,
        expected=expected,
        actual=actual,
    )


class TestRecordedOutputs:
    """What a step returned and what its checks compared are redacted by key too."""

    def test_the_output_is_redacted_by_key(self) -> None:
        record = wire.as_recorded(
            _result(output={"token_type": "Bearer", "jwt": _TOKEN, "nested": {"id_token": "x"}})
        )
        assert record.output == {
            "token_type": "Bearer",
            "jwt": "***",
            "nested": {"id_token": "***"},
        }

    def test_an_output_the_author_revealed_keeps_its_value(self) -> None:
        result = wire.disclose(
            _result(output={"api_key": "mock-api-key-0123", "headers": {"x-api-key": "k"}}),
            wire.Disclosure(shown=frozenset({"api_key"})),
        )
        assert wire.as_recorded(result).output == {
            "api_key": "mock-api-key-0123",
            "headers": {"x-api-key": "***"},
        }

    def test_a_withheld_value_is_masked_in_the_step_s_own_record(self) -> None:
        result = wire.disclose(
            _result(output=["junk-secret-000300", "kept"]),
            wire.Disclosure(withheld=("junk-secret-000300",)),
        )
        assert wire.as_recorded(result).output == ["***", "kept"]

    def test_the_step_s_own_request_url_is_redacted(self) -> None:
        record = wire.as_recorded(
            _result(request=HttpRequest(method="GET", url="https://h/p?api_key=K&page=2"))
        )
        assert record.request.url == "https://h/p?api_key=***&page=2"

    def test_a_check_on_a_credential_field_hides_both_sides(self) -> None:
        record = wire.as_recorded(
            _result(assertions=[_check("access_token", expected="abc", actual=_TOKEN)])
        )
        assert (record.assertions[0].expected, record.assertions[0].actual) == ("***", "***")

    def test_a_document_compared_whole_is_redacted_by_its_keys(self) -> None:
        record = wire.as_recorded(
            _result(
                assertions=[
                    _check("value", expected={"client_secret": _SECRET}, actual={"ok": True})
                ]
            )
        )
        assert record.assertions[0].expected == {"client_secret": "***"}
        assert record.assertions[0].actual == {"ok": True}


class TestInboundCalls:
    """A call the SUT made to a mock is published redacted, the step still gets it whole."""

    def test_the_received_event_redacts_headers_query_and_body(self, tmp_path: Any) -> None:
        from tractusx_testlab.logging.trace import ExecutionTrace
        from tractusx_testlab.models.runtime.events import Listener
        from tractusx_testlab.models.runtime.results import CallbackResult

        received: list[dict[str, Any]] = []
        trace = ExecutionTrace("tck", tmp_path / "trace.jsonl")
        monitor = ExecutionMonitor(MagicMock(), trace)
        monitor.add_callback(lambda _event, payload: received.append(payload))
        request = CallbackResult(
            listener_name="POST:/cb",
            path="/cb",
            headers={"X-Forwarded-Access-Token": "PROXY-TOKEN-1", "Content-Type": "json"},
            query_params={"access_token": "QUERY-TOKEN-1", "page": "1"},
            payload={"dataAddress": {"edc:authorization": _TOKEN, "endpoint": "https://dp"}},
        )

        monitor.on_step_received(
            "job",
            "t",
            "wait",
            "mock/wait/http_request",
            "main",
            Listener(method="POST", url="http://mock/cb", path="/cb"),
            request,
            5,
        )
        trace.close()

        written = str(received) + (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
        for value in ("PROXY-TOKEN-1", "QUERY-TOKEN-1", _TOKEN):
            assert value not in written
        assert "https://dp" in written
        assert request.payload["dataAddress"]["edc:authorization"] == _TOKEN

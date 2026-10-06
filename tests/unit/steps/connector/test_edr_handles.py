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

"""An EDR's token is a handle: it opens its own data plane, and nothing else."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging import wire
from tractusx_testlab.logging.masking import forget_secrets
from tractusx_testlab.logging.wire.redaction import forget_secret_headers
from tractusx_testlab.models import Job, StepDefinition, StepStatus
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.security.credentials import Credential, secret_of
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.connector._edr import edr_token, issued_data_address
from tractusx_testlab.steps.connector.dataplane import DataplaneCallStep, EdrOutput
from tractusx_testlab.steps.digital_twin_registry.consumer import DataplaneParams
from tractusx_testlab.steps.http.request import HttpRequestStep
from tractusx_testlab.steps.step_contract import _dump_payload
from tractusx_testlab.steps.util.log import LogStep

_TOKEN = "eyJhbGciOiJSUzI1NiJ9.edr-token-value"
_REFRESH = "refresh-token-value-0123"
_DATAPLANE = "https://dp.provider.example/api/public"
_ELSEWHERE = "https://collector.example.org/in"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    forget_secret_headers()
    yield
    forget_secrets()
    forget_secret_headers()


def _context(**config: Any) -> StepContext:
    context = StepContext(
        services=ServiceManager(), job=Job(job_id="edr-run"), config=TestlabConfig(**config)
    )
    context.set_variable("edr_token", edr_token(_TOKEN, _DATAPLANE))
    context.set_variable("dataplane_url", _DATAPLANE)
    return context


def _response(url: str = _DATAPLANE) -> MagicMock:
    response = MagicMock(status_code=200, url=url, content=b"{}", text="{}")
    response.headers = MagicMock(raw=[], **{"get.side_effect": {}.get})
    response.json.return_value = {}
    return response


class TestTheDataAddress:
    def test_its_tokens_become_handles_bound_to_their_addresses(self) -> None:
        document = issued_data_address(
            {
                "endpoint": _DATAPLANE,
                "authorization": _TOKEN,
                "refreshToken": _REFRESH,
                "refreshEndpoint": "https://refresh.provider.example/token",
                "expiresIn": "300",
            }
        )
        assert document is not None
        token, refresh = document["authorization"], document["refreshToken"]
        assert isinstance(token, Credential)
        assert isinstance(refresh, Credential)
        assert token.origins == frozenset({"https://dp.provider.example:443"})
        assert refresh.origins == frozenset({"https://refresh.provider.example:443"})
        assert document["endpoint"] == _DATAPLANE
        assert document["expiresIn"] == "300"

    def test_the_run_reads_the_handle_and_every_record_reads_the_marker(self) -> None:
        payload = EdrOutput(dataplane_url=_DATAPLANE, edr_token=edr_token(_TOKEN, _DATAPLANE))

        dumped = _dump_payload(payload)

        assert isinstance(dumped["edr_token"], Credential)
        assert secret_of(dumped["edr_token"]) == _TOKEN
        assert payload.model_dump(mode="json")["edr_token"] == "***"

    def test_no_token_stays_no_token(self) -> None:
        assert edr_token(None, _DATAPLANE) is None
        assert edr_token("", _DATAPLANE) is None


class TestTheDataPlaneStep:
    @pytest.mark.asyncio
    async def test_the_token_is_sent_to_its_own_data_plane(self) -> None:
        context = _context(credential_release=frozenset({"sut"}))
        step = StepDefinition.model_validate(
            {"uses": "connector/dataplane/http_request", "with": {"path": "/data"}}
        )
        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=_response(),
        ) as request:
            result = await run_step(DataplaneCallStep, step, "pull", context)

        assert result.status == StepStatus.PASSED
        assert request.call_args.kwargs["headers"]["Authorization"] == _TOKEN
        assert request.call_args.kwargs["follow_redirects"] is False
        assert _TOKEN not in result.model_dump_json()

    @pytest.mark.asyncio
    async def test_a_reference_handed_over_explicitly_resolves_to_the_handle(self) -> None:
        context = _context()
        context.set_variable("execution.edr.edr_token", context.get_variable("edr_token"))
        step = StepDefinition.model_validate(
            {
                "uses": "connector/dataplane/http_request",
                "with": {
                    "dataplane_url": _DATAPLANE,
                    "edr_token": "${{ execution.edr.edr_token }}",
                },
            }
        )
        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=_response(),
        ) as request:
            result = await run_step(DataplaneCallStep, step, "pull", context)

        assert result.status == StepStatus.PASSED
        assert request.call_args.kwargs["headers"]["Authorization"] == _TOKEN

    @pytest.mark.asyncio
    async def test_pointing_it_elsewhere_sends_nothing(self) -> None:
        context = _context()
        step = StepDefinition.model_validate(
            {"uses": "connector/dataplane/http_request", "with": {"dataplane_url": _ELSEWHERE}}
        )
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as request:
            result = await run_step(DataplaneCallStep, step, "redirect", context)

        assert result.error_code == "CREDENTIAL_ORIGIN_MISMATCH"
        request.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_token_typed_by_the_test_is_sent_as_written(self) -> None:
        context = _context()
        step = StepDefinition.model_validate(
            {"uses": "connector/dataplane/http_request", "with": {"edr_token": ""}}
        )
        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=_response(),
        ) as request:
            await run_step(DataplaneCallStep, step, "negative", context)

        assert request.call_args.kwargs["headers"]["Authorization"] == ""


class TestOtherSteps:
    def test_the_registry_steps_open_it_for_their_base_url_only(self) -> None:
        context = _context()
        base, headers, _ = DataplaneParams().transport(context)
        assert (base, headers["Authorization"]) == (_DATAPLANE, _TOKEN)

        with pytest.raises(Exception, match="may only be sent to"):
            DataplaneParams(dataplane_url=_ELSEWHERE).transport(context)

    def test_an_explicit_empty_token_sends_none_to_a_registry_elsewhere(self) -> None:
        # The e2e engine-toolbox lookup: a mock registry, called with edr_token: "".
        base, headers, _ = DataplaneParams(dataplane_url=_ELSEWHERE, edr_token="").transport(
            _context()
        )
        assert (base, headers["Authorization"]) == (_ELSEWHERE, "")

    @pytest.mark.asyncio
    async def test_http_request_may_send_it_to_its_data_plane_even_when_bindings_are_held(
        self,
    ) -> None:
        context = _context(credential_release=frozenset())
        step = StepDefinition.model_validate(
            {
                "uses": "http/http_request",
                "with": {
                    "url": f"{_DATAPLANE}/shell-descriptors",
                    "headers": {"Authorization": "${{ edr_token }}"},
                },
            }
        )
        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=_response(),
        ) as request:
            result = await run_step(HttpRequestStep, step, "dtr", context)

        assert result.status == StepStatus.PASSED
        assert request.call_args.kwargs["headers"]["Authorization"] == _TOKEN
        assert _TOKEN not in wire.as_recorded(result).model_dump_json()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("uses", "params"),
        [
            ("http/http_request", {"url": _ELSEWHERE, "headers": {"X-T": "${{ edr_token }}"}}),
            ("http/http_request", {"url": _ELSEWHERE, "body": {"t": "${{ edr_token }}"}}),
            ("http/http_request", {"url": f"{_ELSEWHERE}?t=${{{{ edr_token }}}}"}),
            ("util/log", {"message": "token ${{ edr_token }}"}),
        ],
    )
    async def test_it_cannot_be_carried_anywhere_else(
        self, uses: str, params: dict[str, Any]
    ) -> None:
        step_cls = HttpRequestStep if uses == "http/http_request" else LogStep
        context = _context()
        step = StepDefinition.model_validate({"uses": uses, "with": params})
        with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as request:
            result = await run_step(step_cls, step, "exfil", context)

        assert result.status == StepStatus.FAILED
        assert result.error_code in {"CREDENTIAL_MISUSE", "CREDENTIAL_ORIGIN_MISMATCH"}
        request.assert_not_called()
        assert _TOKEN not in result.model_dump_json()


@pytest.mark.parametrize(("operator", "passed"), [("not_null", True), ("not_empty", True)])
def test_a_presence_check_on_the_handle_still_holds(operator: str, passed: bool) -> None:
    from tractusx_testlab.models import Assertion
    from tractusx_testlab.steps.assertions import AssertionEngine
    from tractusx_testlab.steps.step_contract import StepOutput

    output = StepOutput(value={"edr_token": edr_token(_TOKEN, _DATAPLANE)})
    check = Assertion(
        uses="validate/assert", **{"with": {"input": "edr_token", "operator": operator}}
    )

    (result,) = AssertionEngine.evaluate([check], output)

    assert result.passed is passed
    assert _TOKEN not in result.model_dump_json()


def test_the_handle_s_value_is_masked_in_every_record_of_the_run() -> None:
    from tractusx_testlab.logging.masking import mask
    from tractusx_testlab.player.execution._step_outputs import hide_secrets
    from tractusx_testlab.steps.connector.dataplane import GetEdrStep
    from tractusx_testlab.steps.step_contract import StepOutput

    document = issued_data_address(
        {"endpoint": _DATAPLANE, "authorization": _TOKEN, "refreshToken": _REFRESH}
    )
    output = StepOutput(
        value={
            "dataplane_url": _DATAPLANE,
            "edr_token": edr_token(_TOKEN, _DATAPLANE),
            "data_address": document,
        }
    )

    hide_secrets(GetEdrStep, StepDefinition(uses="connector/consumer/get_edr"), output, run="r")

    assert mask(f"echo {_TOKEN} {_REFRESH}") == "echo *** ***"

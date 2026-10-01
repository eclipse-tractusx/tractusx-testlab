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

"""A credential handle resolves only as the whole value of a header that carries it."""

from __future__ import annotations

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.loading.resolver import resolve_params, try_resolve_params
from tractusx_testlab.security.credentials import Credential, CredentialMisuseError
from tractusx_testlab.services.instances import ServiceManager

_SECRET = "platform-management-key-0123"
_NAME = "infrastructure.engine.connector.api_key"
_REF = f"${{{{ {_NAME} }}}}"
_HEADERS = frozenset({"headers"})


@pytest.fixture()
def handle() -> Credential:
    return Credential(_SECRET, name=_NAME, side="engine", origins=["https://cp.example.com:443"])


@pytest.fixture()
def context(handle: Credential) -> StepContext:
    context = StepContext(
        services=ServiceManager(), job=Job(job_id="run-1"), config=TestlabConfig()
    )
    context.set_variable(_NAME, handle)
    return context


class TestWhereAHandleResolves:
    def test_the_whole_value_of_a_carried_header_is_the_handle(
        self, context: StepContext, handle: Credential
    ) -> None:
        resolved = resolve_params(
            {"headers": {"x-api-key": _REF, "Accept": "application/json"}},
            context,
            credential_params=_HEADERS,
        )
        assert resolved["headers"]["x-api-key"] is handle
        assert resolved["headers"]["Accept"] == "application/json"

    def test_a_static_env_value_naming_it_is_followed_to_the_handle(
        self, context: StepContext, handle: Credential
    ) -> None:
        context.set_template("connector_key", _REF)
        resolved = resolve_params(
            {"headers": {"x-api-key": "${{ env.connector_key }}"}},
            context,
            credential_params=_HEADERS,
        )
        assert resolved["headers"]["x-api-key"] is handle


class TestWhereItIsRefused:
    @pytest.mark.parametrize(
        "params",
        [
            {"headers": {"Authorization": f"Bearer {_REF}"}},
            {"url": f"https://evil.io/?k={_REF}"},
            {"url": _REF},
            {"body": {"key": _REF}},
            {"body": f"key={_REF}"},
            {"query_params": {"k": _REF}},
            {"message": _REF},
        ],
    )
    def test_any_other_position_fails(self, context: StepContext, params: dict) -> None:
        with pytest.raises(CredentialMisuseError) as caught:
            resolve_params(params, context, credential_params=_HEADERS)
        assert caught.value.code == "CREDENTIAL_MISUSE"
        assert _SECRET not in str(caught.value)

    def test_a_step_that_carries_no_credential_takes_none_even_whole(
        self, context: StepContext
    ) -> None:
        with pytest.raises(CredentialMisuseError):
            resolve_params({"headers": {"x-api-key": _REF}}, context)

    def test_a_document_holding_a_handle_is_refused(
        self, context: StepContext, handle: Credential
    ) -> None:
        context.set_variable("execution.copy.value", {"nested": [handle]})
        with pytest.raises(CredentialMisuseError):
            resolve_params({"body": "${{ execution.copy.value }}"}, context)

    def test_test_data_that_embeds_it_is_refused(self, context: StepContext) -> None:
        context.set_template("testdata.body", {"auth": _REF})
        with pytest.raises(CredentialMisuseError):
            resolve_params(
                {"headers": {"x": "${{ testdata.body }}"}}, context, credential_params=_HEADERS
            )

    def test_the_tolerant_resolver_answers_none_and_leaks_nothing(
        self, context: StepContext
    ) -> None:
        assert try_resolve_params({"url": f"https://x/{_REF}"}, context) is None

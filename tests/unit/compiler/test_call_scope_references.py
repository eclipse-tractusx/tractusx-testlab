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

"""The compiler's view of call-scoped references — ``${{ *.request.* }}`` and ``${{ *.process.* }}``.

They are in scope inside ``labs/mock/api/dynamic`` — its ``process`` and its
reply — and nowhere else, and ``*.process.<id>`` names only a step of that
mock's own ``process``. The ids of those steps are no phase names: they
publish per call, never under ``execution.``.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.compiler.validation.validator import TestValidator, _scope_of
from tractusx_testlab.models import StepDefinition, TestDefinition
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition


def _mint(step_id: str) -> dict:
    return {"id": step_id, "uses": "util/generate_uuid", "returns": {"value": {"type": "string"}}}


def _log(value: str) -> dict:
    return {"uses": "util/log", "with": {"message": "m", "value": value}}


def _mock(process: list[dict], **reply: Any) -> StepDefinition:
    return StepDefinition(
        id="endpoint",
        uses="labs/mock/api/dynamic",
        with_={"path": "/p", "process": process, **reply},
    )


def _errors(*steps: StepDefinition) -> list[str]:
    test = TestDefinition(
        syntax="v1-alpha",
        kind="test",
        id="t",
        namespace="n",
        metadata={"name": "t"},
        execution=list(steps),
    )
    tck = TckDefinition(
        kind="tck",
        syntax="v1-alpha",
        id="tck",
        metadata=TckMetadataDefinition(name="tck", version="1.0"),
    )
    result = TestValidator().validate(test, scope=_scope_of(tck, test))
    return [issue.message for issue in result.issues if issue.level == "error"]


class TestInsideTheMock:
    def test_the_reply_reads_the_request_and_a_path_into_it(self) -> None:
        assert _errors(_mock([], response_body="${{ *.request.body.header.messageId }}")) == []

    def test_a_step_of_the_process_reads_the_request(self) -> None:
        assert _errors(_mock([_log("${{ *.request.headers }}")])) == []

    def test_the_reply_reads_a_step_of_the_process(self) -> None:
        mock = _mock([_mint("answer_id")], response_status="${{ *.process.answer_id.value }}")
        assert _errors(mock) == []

    def test_a_step_nested_in_a_branch_of_the_process_is_in_scope(self) -> None:
        branch = {
            "id": "pick",
            "uses": "flow/if",
            "with": {
                "conditions": [{"input": "${{ *.request.body }}", "operator": "not_null"}],
                "then": [_mint("verdict")],
                "else": [_mint("verdict")],
            },
        }
        assert _errors(_mock([branch], response_body="${{ *.process.verdict.value }}")) == []

    def test_the_reply_still_reads_what_the_test_knows(self) -> None:
        assert _errors(_mock([], response_body={"id": "${{ execution.id }}"})) == []


class TestOutsideTheMock:
    def test_a_call_scoped_reference_elsewhere_is_refused_and_explained(self) -> None:
        (error,) = _errors(
            StepDefinition(uses="util/log", with_=_log("${{ *.request.body }}")["with"])
        )
        assert "only inside labs/mock/api/dynamic" in error

    def test_a_request_field_that_does_not_exist_is_refused(self) -> None:
        (error,) = _errors(_mock([], response_body="${{ *.request.cookies }}"))
        assert "*.request.cookies" in error

    def test_a_process_id_no_step_has_is_refused(self) -> None:
        (error,) = _errors(_mock([_mint("answer_id")], response_body="${{ *.process.nope.value }}"))
        assert "*.process.nope.value" in error

    def test_a_process_step_is_no_phase_name(self) -> None:
        after = StepDefinition(
            uses="util/log", with_=_log("${{ execution.answer_id.value }}")["with"]
        )
        (error,) = _errors(_mock([_mint("answer_id")]), after)
        assert "execution.answer_id.value" in error

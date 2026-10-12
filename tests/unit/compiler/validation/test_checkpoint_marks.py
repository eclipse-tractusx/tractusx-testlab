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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A ``checkpoint:`` mark the run could not honour fails validation (ADR-0027)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import tractusx_testlab.steps  # noqa: F401 — registers the steps the marks are on
from tractusx_testlab.compiler.validation._checkpoint_marks import checkpoint_findings
from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.models import TestDefinition


def _test(*steps: dict) -> TestDefinition:
    return TestDefinition.model_validate(
        {
            "syntax": "v1-alpha",
            "id": "t",
            "namespace": "n",
            "metadata": {"name": "t", "version": "1"},
            "execution": list(steps),
        }
    )


_WAIT = {"id": "await", "uses": "mock/wait/http_request", "with": {"mock": "x"}}


def test_a_label_and_a_switch_are_fine_on_any_step() -> None:
    test = _test(
        {**_WAIT, "checkpoint": {"label": "Call us", "description": "Now"}},
        {"uses": "util/log", "with": {"message": "m"}, "checkpoint": True},
        {"uses": "flow/select", "with": {"options": ["a"]}, "checkpoint": False},
    )
    assert list(checkpoint_findings(test)) == []


def test_a_declared_direction_cannot_be_changed() -> None:
    test = _test({**_WAIT, "checkpoint": {"direction": "outbound"}})
    [(phase, index, field, message)] = checkpoint_findings(test)
    assert (phase, index, field) == ("execution", 0, "checkpoint")
    assert "inbound checkpoint by its type" in message


def test_an_internal_mark_has_no_via() -> None:
    test = _test(
        {
            "uses": "util/log",
            "with": {"message": "m"},
            "checkpoint": {"direction": "internal", "via": "direct"},
        }
    )
    assert "calls nothing" in next(iter(checkpoint_findings(test)))[3]


def test_a_nested_mark_is_checked_and_reported_on_its_flow_step() -> None:
    nested = {**_WAIT, "checkpoint": {"via": "dataplane"}}
    test = _test({"uses": "flow/retry", "with": {"steps": [nested]}})
    assert [finding[:3] for finding in checkpoint_findings(test)] == [
        ("execution", 0, "checkpoint")
    ]


def test_the_validator_reports_it_as_an_error() -> None:
    result = TestValidator().validate(_test({**_WAIT, "checkpoint": {"direction": "internal"}}))
    assert not result.valid
    assert any(issue.field == "checkpoint" for issue in result.issues)


def test_an_unknown_key_in_the_mark_is_refused_by_the_model() -> None:
    with pytest.raises(ValidationError):
        _test({**_WAIT, "checkpoint": {"lable": "typo"}})

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5, Claude Opus 5.5).
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""How the engine reads a ``validate:`` entry's ``severity``.

The value is read in any case — a TCK written with ``severity: soft`` used to
stop the run with a ``ValueError`` from the enum. A value that is no severity
at all is reported as a failed HARD check that names it, as any other
assertion the engine cannot understand is.
"""

from __future__ import annotations

import pytest

from tractusx_testlab.models import AssertionSeverity
from tractusx_testlab.models.authoring.definitions import Assertion
from tractusx_testlab.steps.assertions import AssertionEngine


def _run(severity: object, value: object = None):
    params = {"input": "value", "operator": "not_null", "severity": severity}
    return AssertionEngine.evaluate(
        [Assertion(uses="validate/assert", **{"with": params})], {"value": value}
    )[0]


class TestSeverityCase:
    @pytest.mark.parametrize(
        ("written", "member"),
        [
            ("HARD", AssertionSeverity.HARD),
            ("hard", AssertionSeverity.HARD),
            ("Hard", AssertionSeverity.HARD),
            ("SOFT", AssertionSeverity.SOFT),
            ("soft", AssertionSeverity.SOFT),
        ],
    )
    def test_the_enum_reads_a_severity_in_any_case(
        self, written: str, member: AssertionSeverity
    ) -> None:
        assert AssertionSeverity(written) is member

    def test_the_enum_still_refuses_any_other_word(self) -> None:
        with pytest.raises(ValueError):
            AssertionSeverity("warning")

    def test_a_lower_case_soft_failure_is_a_warning(self) -> None:
        result = _run("soft")
        assert (result.passed, result.severity) == (False, AssertionSeverity.SOFT)
        assert AssertionEngine.has_hard_failure([result]) is False

    def test_a_lower_case_hard_failure_fails_the_step(self) -> None:
        assert AssertionEngine.has_hard_failure([_run("hard")]) is True


class TestUnknownSeverity:
    def test_an_unknown_severity_is_a_failed_hard_check_not_a_crash(self) -> None:
        result = _run("warning", value="present")
        assert (result.passed, result.severity) == (False, AssertionSeverity.HARD)
        assert "'warning'" in result.message

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Tests that the compiler rejects the banned ``uses:`` prefixes (ADR-0021)."""

from __future__ import annotations

from typing import Any

from tractusx_testlab.compiler.validation._manifest_validation import _reject_banned_steps


class TestRejectDeprecatedVerbs:
    """Compiler must reject precondition/* steps with an actionable error."""

    def test_rejects_precondition_provide_in_setup(self) -> None:
        test_data: dict[str, Any] = {
            "setup": [
                {"id": "my_policy", "uses": "precondition/provide", "with": {"value": "x"}},
            ],
            "execution": [],
        }

        errors = _reject_banned_steps(test_data, "tests/example.yaml")

        assert len(errors) == 1
        assert "precondition/provide" in errors[0]
        assert "ADR-0021" in errors[0]
        assert "my_policy" in errors[0]

    def test_rejects_precondition_in_execution_phase(self) -> None:
        test_data: dict[str, Any] = {
            "setup": [],
            "execution": [
                {"id": "pre", "uses": "precondition/check"},
            ],
        }

        errors = _reject_banned_steps(test_data, "tests/bad.yaml")

        assert len(errors) == 1
        assert "precondition/check" in errors[0]

    def test_accepts_valid_verbs(self) -> None:
        test_data: dict[str, Any] = {
            "setup": [
                {"id": "mock", "uses": "mock/endpoint"},
                {"id": "asset", "uses": "connector/create-asset"},
            ],
            "execution": [
                {"id": "req", "uses": "http/request"},
            ],
        }

        errors = _reject_banned_steps(test_data, "tests/valid.yaml")

        assert errors == []

    def test_handles_missing_phases(self) -> None:
        test_data: dict[str, Any] = {"execution": []}

        errors = _reject_banned_steps(test_data, "tests/minimal.yaml")

        assert errors == []

    def test_error_message_suggests_migration_path(self) -> None:
        test_data: dict[str, Any] = {
            "setup": [
                {"id": "pol", "uses": "precondition/provide", "with": {"value": "policy"}},
            ],
        }

        errors = _reject_banned_steps(test_data, "tests/migrate.yaml")

        assert "env.variables" in errors[0]
        assert "config/connector/policy" in errors[0]


class TestRejectStandaloneValidateSteps:
    """``validate/*`` is an assertion, not a step of its own — the second table row."""

    def test_rejects_a_validate_step_in_execution(self) -> None:
        test_data: dict[str, Any] = {
            "execution": [
                {"id": "check", "uses": "validate/assert", "with": {"input": "x"}},
            ],
        }

        errors = _reject_banned_steps(test_data, "tests/standalone.yaml")

        assert len(errors) == 1
        assert "validate/assert" in errors[0]
        assert "check" in errors[0]
        assert "'validate:' block" in errors[0]

    def test_rejects_a_validate_step_in_teardown(self) -> None:
        test_data: dict[str, Any] = {
            "teardown": [{"id": "late", "uses": "validate/field"}],
        }

        assert len(_reject_banned_steps(test_data, "tests/teardown.yaml")) == 1

    def test_an_inline_validate_block_is_untouched(self) -> None:
        """The rule reads ``uses``; assertions live under a step, not beside one."""
        test_data: dict[str, Any] = {
            "execution": [
                {
                    "id": "fetch",
                    "uses": "http/http_request",
                    "validate": [{"uses": "validate/assert", "with": {"input": "x"}}],
                },
            ],
        }

        assert _reject_banned_steps(test_data, "tests/inline.yaml") == []

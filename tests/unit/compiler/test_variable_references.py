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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""How a test may reference a variable the manifest declares.

A variable is one value and its id names all of it. A path into it —
``${{ env.usage_policy.policy }}`` or ``${{ env.usage_policy.value }}`` — is
rejected at compile time, at the line that has to change.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.compiler.validation._variable_references import (
    declared_variable_ids,
    validate_variable_references,
)


def _env(*entries: dict[str, Any]) -> dict[str, Any]:
    return {"variables": list(entries)}


def _policy() -> dict[str, Any]:
    return {
        "id": "usage_policy",
        "uses": "config/connector/policy",
        "with": {"value": {"permissions": [{"action": "use"}]}},
        "returns": {"value": {"type": "object", "class": "Policy"}},
    }


class TestReferencesIntoAVariable:
    def test_a_reference_to_the_old_artifact_key_is_rejected(self) -> None:
        test_data = {
            "execution": [
                {
                    "id": "pull",
                    "uses": "connector/consumer/pull_data_filtered",
                    "with": {"expected_policies": "${{ env.usage_policy.policy }}"},
                }
            ]
        }

        errors = validate_variable_references(
            test_data, declared_variable_ids(_env(_policy())), "tests/pull.yaml"
        )

        assert len(errors) == 1
        assert "reaches into variable" in errors[0]
        assert "${{ env.usage_policy }}" in errors[0]

    def test_the_publishing_key_is_rejected_too(self) -> None:
        """``.value`` is the key the artifact key became — still a path, not a name."""
        test_data = {
            "execution": [
                {
                    "id": "pull",
                    "uses": "connector/consumer/pull_data_filtered",
                    "with": {"expected_policies": "${{ env.usage_policy.value }}"},
                }
            ]
        }

        errors = validate_variable_references(
            test_data, declared_variable_ids(_env(_policy())), "tests/pull.yaml"
        )

        assert len(errors) == 1
        assert "${{ env.usage_policy }}" in errors[0]

    def test_the_whole_variable_passes(self) -> None:
        test_data = {
            "execution": [
                {
                    "id": "pull",
                    "uses": "connector/consumer/pull_data_filtered",
                    "with": {"expected_policies": "${{ env.usage_policy }}"},
                }
            ]
        }

        ids = declared_variable_ids(_env(_policy()))

        assert validate_variable_references(test_data, ids, "tests/pull.yaml") == []

    def test_testdata_and_step_outputs_are_left_alone(self) -> None:
        """Only a declared variable's id is a variable; the other roots are not."""
        test_data = {
            "execution": [
                {
                    "id": "check",
                    "uses": "validate/schema",
                    "with": {
                        "schema": "${{ env.schemas.cert }}",
                        "input": "${{ execution.pull.dataplane_url }}",
                    },
                }
            ]
        }

        ids = declared_variable_ids(_env(_policy()))

        assert validate_variable_references(test_data, ids, "tests/check.yaml") == []

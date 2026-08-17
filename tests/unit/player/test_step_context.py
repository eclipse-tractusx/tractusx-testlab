#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Tests for StepContext — the execution context passed to every step."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.player.execution.context import StepContext


@pytest.fixture()
def context() -> StepContext:
    """Build a real StepContext with mocked dependencies."""
    mock_services = MagicMock()
    mock_job = MagicMock()
    mock_config = MagicMock()
    return StepContext(services=mock_services, job=mock_job, config=mock_config)


class TestStepContextVariables:
    """Tests for StepContext variable get/set/has."""

    def test_set_and_get_variable(self, context: StepContext) -> None:
        context.set_variable("asset_id", "abc-123")
        assert context.get_variable("asset_id") == "abc-123"

    def test_get_variable_returns_default_when_missing(self, context: StepContext) -> None:
        assert context.get_variable("missing", "fallback") == "fallback"

    def test_get_variable_returns_none_when_no_default(self, context: StepContext) -> None:
        assert context.get_variable("nope") is None

    def test_has_variable_true_when_set(self, context: StepContext) -> None:
        context.set_variable("x", 42)
        assert context.has_variable("x") is True

    def test_has_variable_false_when_not_set(self, context: StepContext) -> None:
        assert context.has_variable("nonexistent") is False

    def test_variables_property_returns_copy(self, context: StepContext) -> None:
        context.set_variable("a", 1)
        context.set_variable("b", 2)
        variables = context.variables
        assert variables == {"a": 1, "b": 2}
        variables["c"] = 3
        assert context.has_variable("c") is False

    def test_overwrite_variable(self, context: StepContext) -> None:
        context.set_variable("key", "old")
        context.set_variable("key", "new")
        assert context.get_variable("key") == "new"


class TestStepContextProperties:
    """Tests for StepContext property accessors."""

    def test_config_property(self, context: StepContext) -> None:
        assert context.config is not None

    def test_job_property(self, context: StepContext) -> None:
        assert context.job is not None

    def test_services_property(self, context: StepContext) -> None:
        assert context.services is not None

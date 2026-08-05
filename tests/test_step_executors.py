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

"""Tests for StepRegistry and individual step executor classes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps.base import BaseStep, StepOutput

# Ensure all built-in steps are registered
import tractusx_testlab.steps  # noqa: F401


class TestStepRegistry:
    """Tests for the StepRegistry lookup mechanism."""

    def test_registry_has_export_variable_step(self) -> None:
        cls = StepRegistry.get("util/export_env", "saturn")
        assert cls is not None
        assert issubclass(cls, BaseStep)

    def test_registry_returns_none_for_unknown_step(self) -> None:
        cls = StepRegistry.get("nonexistent_step_xyz_123", "saturn")
        assert cls is None

    def test_registry_has_method_checks_existence(self) -> None:
        assert StepRegistry.has("util/export_env", "saturn") is True
        assert StepRegistry.has("fake_step_not_real", "saturn") is False

    def test_list_step_types_returns_nonempty(self) -> None:
        types = StepRegistry.list_step_types()
        assert len(types) > 0
        assert "util/export_env" in types

    def test_list_step_types_with_version_filter(self) -> None:
        types = StepRegistry.list_step_types("saturn")
        assert isinstance(types, list)
        assert "util/export_env" in types


class TestExportVariableStep:
    """Tests for the export_variable step executor."""

    @pytest.mark.asyncio
    async def test_export_variable_reads_from_context(self, mock_context: MagicMock) -> None:
        # Arrange
        mock_context.set_variable("my_var", "hello_world")
        cls = StepRegistry.get("util/export_env", "saturn")
        assert cls is not None
        step_instance = cls()
        definition = MagicMock()

        # Act
        output = await step_instance.execute(
            {"name": "my_var"}, mock_context, definition
        )

        # Assert
        assert isinstance(output, StepOutput)

    @pytest.mark.asyncio
    async def test_export_variable_with_missing_var(self, mock_context: MagicMock) -> None:
        # Arrange
        cls = StepRegistry.get("util/export_env", "saturn")
        assert cls is not None
        step_instance = cls()
        definition = MagicMock()

        # Act
        output = await step_instance.execute(
            {"name": "unset_var"}, mock_context, definition
        )

        # Assert
        assert isinstance(output, StepOutput)

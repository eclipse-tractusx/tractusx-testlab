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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.


"""An extension can add ``with:`` parameters to an existing step.

The keys are written like the step's own; the model and the behaviour live in
the extension. These pin that the step never sees them, that the extension runs
only when they are written, that a bad value fails the step in the extension's
name, that the compiler refuses them without the extension, and that the step
reference lists them as experimental.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import yaml

from tractusx_testlab.authoring.step_docs import render_step
from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.models import TckDefinition
from tractusx_testlab.models.authoring.definitions import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.steps.step_extension import (
    ExtensionParams,
    StepExtension,
    extends,
    unregister,
)
from tractusx_testlab.steps.util.log import LogStep

SEEN: list[Any] = []


class ShoutParams(ExtensionParams):
    """Keys the throwaway extension adds to util/log."""

    shout: bool = False


class Shout(StepExtension[ShoutParams]):
    """Records what it was given, then runs the step."""

    params_model = ShoutParams

    async def around(self, params, context, definition, proceed):
        SEEN.append(params.shout)
        output = await proceed()
        SEEN.append(output.value)
        return output


@pytest.fixture
def shout() -> Iterator[type[Shout]]:
    SEEN.clear()
    registered = extends("util/log", extension="labs")(Shout)
    yield registered
    unregister(registered)


def _log(**with_: Any) -> StepDefinition:
    return StepDefinition(id="act", uses="util/log", with_={"message": "hi", **with_})


class TestTheRunner:
    async def test_the_extension_runs_around_the_step(self, shout, mock_context) -> None:
        definition = _log(value="v", shout=True)
        result = await run_step(LogStep, definition, "act", mock_context, dict(definition.with_))
        assert result.status is StepStatus.PASSED, result.error
        assert SEEN == [True, "v"]

    async def test_the_step_never_sees_the_key(self, shout, mock_context) -> None:
        """util/log rejects unknown keys — passing proves the key was taken out first."""
        result = await run_step(LogStep, _log(shout=True), "act", mock_context)
        assert result.status is StepStatus.PASSED, result.error

    async def test_an_extension_whose_keys_are_not_written_does_not_run(
        self, shout, mock_context
    ) -> None:
        result = await run_step(LogStep, _log(), "act", mock_context)
        assert result.status is StepStatus.PASSED
        assert SEEN == []

    async def test_a_bad_value_fails_the_step_in_the_extensions_name(
        self, shout, mock_context
    ) -> None:
        result = await run_step(LogStep, _log(shout={"not": "a bool"}), "act", mock_context)
        assert result.status is StepStatus.FAILED
        assert "experimental extension 'labs'" in result.error

    async def test_without_the_extension_the_key_is_an_unknown_parameter(
        self, mock_context
    ) -> None:
        result = await run_step(LogStep, _log(shout=True), "act", mock_context)
        assert result.status is StepStatus.FAILED
        assert "shout" in result.error

    async def test_a_key_the_step_already_has_is_an_engine_fault(self, mock_context) -> None:
        class MessageParams(ExtensionParams):
            message: str = ""

        class Clash(StepExtension[MessageParams]):
            params_model = MessageParams

        registered = extends("util/log", extension="labs")(Clash)
        try:
            result = await run_step(LogStep, _log(), "act", mock_context)
        finally:
            unregister(registered)
        assert result.status is StepStatus.FAILED
        assert result.error_origin == "engine"
        assert "message" in result.error


class TestRegistration:
    def test_an_unknown_extension_is_refused_at_import(self) -> None:
        with pytest.raises(TypeError, match="not registered"):
            extends("util/log", extension="nope")(Shout)

    def test_an_undeclared_parameter_model_is_refused_at_import(self) -> None:
        class Undeclared(StepExtension[ShoutParams]):
            pass

        with pytest.raises(TypeError, match="params_model"):
            extends("util/log", extension="labs")(Undeclared)


def _errors(tmp_path, extensions: list[str]) -> list:
    manifest = {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "params-tck",
        "metadata": {"name": "Params"},
        "extensions": extensions,
        "tests": [{"id": "t.yaml"}],
    }
    test = {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "t",
        "namespace": "params-tck",
        "metadata": {"name": "t"},
        "execution": [
            {
                "id": "act",
                "name": "Act",
                "uses": "util/log",
                "with": {"message": "hi", "shout": True},
            }
        ],
    }
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.yaml").write_text(yaml.dump(test), encoding="utf-8")
    issues = TestValidator().validate_tck(TckDefinition.model_validate(manifest), tmp_path).issues
    return [issue for issue in issues if issue.level == "error"]


class TestTheCompiler:
    def test_the_parameter_is_refused_without_the_extension(self, shout, tmp_path) -> None:
        (error,) = _errors(tmp_path, [])
        assert error.field == "with.shout"
        assert "extensions: [labs]" in error.message

    def test_the_parameter_is_accepted_with_it(self, shout, tmp_path) -> None:
        assert _errors(tmp_path, ["labs"]) == []


class TestTheStepReference:
    def test_the_step_lists_the_parameter_as_experimental(self, shout) -> None:
        page = "\n".join(render_step(LogStep))
        assert "**Experimental inputs** — extension `labs`" in page
        assert "| `shout` |" in page

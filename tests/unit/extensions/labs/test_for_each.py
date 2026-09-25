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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Tests for ``labs/flow/for_each`` — a nested sequence run once per item."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.extensions.labs.steps.for_each import EACH_INDEX, EACH_ITEM, ForEachStep
from tractusx_testlab.models import Job, StepDefinition, TckDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.services.instances import ServiceManager


@pytest.fixture()
def context() -> StepContext:
    """A real context: the loop binds and unbinds names the nested steps resolve."""
    return StepContext(services=ServiceManager(), job=Job(job_id="run-1"), config=TestlabConfig())


def _loop(steps: list[dict], items: Any = "${{ env.ids }}") -> StepDefinition:
    return StepDefinition(
        id="loop", uses="labs/flow/for_each", with_={"items": items, "steps": steps}
    )


def _log(value: str) -> dict:
    return {"uses": "util/log", "with": {"message": "item", "value": value}}


class TestForEachStep:
    @pytest.mark.asyncio
    async def test_the_nested_steps_run_once_per_item_with_that_item(
        self, context: StepContext
    ) -> None:
        context.set_variable("ids", ["a", "b"])

        result = await run_step(ForEachStep, _loop([_log("${{ each.item }}")]), "s", context)

        assert result.output == {"iterations": 2, "outputs": [["a"], ["b"]]}

    @pytest.mark.asyncio
    async def test_the_index_counts_from_zero(self, context: StepContext) -> None:
        result = await run_step(
            ForEachStep, _loop([_log("${{ each.index }}")], items=["x", "y"]), "s", context
        )

        assert result.output["outputs"] == [[0], [1]]

    @pytest.mark.asyncio
    async def test_an_empty_list_runs_nothing_and_passes(self, context: StepContext) -> None:
        result = await run_step(
            ForEachStep, _loop([_log("${{ each.item }}")], items=[]), "s", context
        )

        assert result.output == {"iterations": 0, "outputs": []}

    @pytest.mark.asyncio
    async def test_the_loop_names_are_gone_once_it_ends(self, context: StepContext) -> None:
        await run_step(ForEachStep, _loop([_log("${{ each.item }}")], items=["a"]), "s", context)

        assert not context.has_variable(EACH_ITEM)
        assert not context.has_variable(EACH_INDEX)

    @pytest.mark.asyncio
    async def test_an_inner_loop_hands_the_outer_item_back(self, context: StepContext) -> None:
        inner = {"uses": "labs/flow/for_each", "with": {"items": [1, 2], "steps": [_log("x")]}}

        result = await run_step(
            ForEachStep, _loop([inner, _log("${{ each.item }}")], items=["outer"]), "s", context
        )

        assert result.output["outputs"][0][1] == "outer"

    @pytest.mark.asyncio
    async def test_a_nested_step_reads_the_one_before_it_in_the_same_item(
        self, context: StepContext
    ) -> None:
        context.bind_step_namespace("teardown")
        mint = {
            "id": "mint",
            "uses": "util/generate_uuid",
            "returns": {"value": {"type": "string"}},
        }

        result = await run_step(
            ForEachStep,
            _loop([mint, _log("${{ teardown.mint.value }}")], items=["a", "b"]),
            "s",
            context,
        )

        (first_minted, first_read), (second_minted, second_read) = result.output["outputs"]
        assert first_read == first_minted
        assert second_read == second_minted
        assert first_minted != second_minted

    @pytest.mark.asyncio
    async def test_a_failing_nested_step_fails_the_loop_and_names_the_item(
        self, context: StepContext
    ) -> None:
        result = await run_step(
            ForEachStep, _loop([{"uses": "no/such/step"}], items=["a"]), "s", context
        )

        assert result.error is not None
        assert "item 0 ('a')" in result.error

    @pytest.mark.asyncio
    async def test_a_nested_step_is_not_resolved_before_the_loop_runs(self) -> None:
        """A MagicMock context has no 'each.item' until the loop sets one."""
        ctx = MagicMock()
        ctx.invoke_step = run_step

        output = await ForEachStep().invoke(
            {"items": [], "steps": [_log("${{ each.item }}")]}, ctx, _loop([])
        )

        assert output.value["iterations"] == 0


def _errors(tmp_path, step: dict) -> list[str]:
    manifest = {
        "syntax": "v1-alpha",
        "kind": "tck",
        "id": "loop-tck",
        "metadata": {"name": "Loop"},
        "extensions": ["labs"],
        "env": {
            "variables": [{"id": "ids", "uses": "variable/type/string", "with": {"value": "a"}}]
        },
        "tests": [{"id": "t.yaml"}],
    }
    test = {
        "syntax": "v1-alpha",
        "kind": "test",
        "id": "t",
        "namespace": "loop-tck",
        "metadata": {"name": "t"},
        "execution": [step],
    }
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.yaml").write_text(yaml.dump(test), encoding="utf-8")
    issues = TestValidator().validate_tck(TckDefinition.model_validate(manifest), tmp_path).issues
    return [issue.message for issue in issues if issue.level == "error"]


class TestTheCompiler:
    def test_a_nested_step_may_read_the_item(self, tmp_path) -> None:
        step = {
            "id": "loop",
            "uses": "labs/flow/for_each",
            "with": {"items": "${{ env.ids }}", "steps": [_log("${{ each.item }}")]},
        }

        assert _errors(tmp_path, step) == []

    def test_the_item_is_refused_outside_the_loop(self, tmp_path) -> None:
        step = {"id": "log", "uses": "util/log", "with": {"message": "${{ each.item }}"}}

        (error,) = _errors(tmp_path, step)
        assert "each.item" in error

    def test_an_unknown_name_inside_the_loop_is_still_refused(self, tmp_path) -> None:
        step = {
            "id": "loop",
            "uses": "labs/flow/for_each",
            "with": {"items": [1], "steps": [_log("${{ env.nope }}")]},
        }

        (error,) = _errors(tmp_path, step)
        assert "env.nope" in error

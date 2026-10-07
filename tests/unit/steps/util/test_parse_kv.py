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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Tests for util/parse_kv — parsing EDC subprotocolBody-style key=value strings."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.util.parse_kv import ParseKvStep

# A realistic EDC subprotocolBody: the dspEndpoint value itself contains '='.
_BODY = "dspEndpoint=https://provider.example/api/v1/dsp?foo=bar;id=urn:uuid:1234-5678"


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinition:
    return StepDefinition(id="parse", uses="util/parse_kv")


class TestParseKvStep:
    @pytest.mark.asyncio
    async def test_selects_single_key(self, context: StepContext) -> None:
        output = await ParseKvStep().invoke(
            {"input": _BODY, "select": "id"},
            context,
            _definition(),
        )
        assert output.value == "urn:uuid:1234-5678"

    @pytest.mark.asyncio
    async def test_value_containing_separator_is_preserved(self, context: StepContext) -> None:
        # Only the first '=' splits the pair, so the query string survives.
        output = await ParseKvStep().invoke(
            {"input": _BODY, "select": "dspEndpoint"},
            context,
            _definition(),
        )
        assert output.value == "https://provider.example/api/v1/dsp?foo=bar"

    @pytest.mark.asyncio
    async def test_returns_whole_dict_without_select(self, context: StepContext) -> None:
        output = await ParseKvStep().invoke({"input": _BODY}, context, _definition())
        assert output.value == {
            "dspEndpoint": "https://provider.example/api/v1/dsp?foo=bar",
            "id": "urn:uuid:1234-5678",
        }

    @pytest.mark.asyncio
    async def test_stores_in_variable(self, context: StepContext) -> None:
        await ParseKvStep().invoke(
            {"input": _BODY, "select": "id", "store_in_variable": "asset_id"},
            context,
            _definition(),
        )
        assert context.get_variable("asset_id") == "urn:uuid:1234-5678"

    @pytest.mark.asyncio
    async def test_custom_separators(self, context: StepContext) -> None:
        output = await ParseKvStep().invoke(
            {"input": "a:1|b:2", "pair_separator": "|", "kv_separator": ":", "select": "b"},
            context,
            _definition(),
        )
        assert output.value == "2"

    @pytest.mark.asyncio
    async def test_whitespace_is_trimmed(self, context: StepContext) -> None:
        output = await ParseKvStep().invoke(
            {"input": " a = 1 ; b = 2 "},
            context,
            _definition(),
        )
        assert output.value == {"a": "1", "b": "2"}

    @pytest.mark.asyncio
    async def test_missing_select_key_raises(self, context: StepContext) -> None:
        with pytest.raises(KeyError, match="'missing' not found"):
            await ParseKvStep().invoke(
                {"input": _BODY, "select": "missing"},
                context,
                _definition(),
            )

    @pytest.mark.asyncio
    async def test_missing_input_raises(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="input: required key 'input' is missing"):
            await ParseKvStep().invoke({"select": "id"}, context, _definition())

    @pytest.mark.asyncio
    async def test_non_string_input_raises(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="input: Input should be a valid string"):
            await ParseKvStep().invoke(
                {"input": {"a": 1}, "select": "id"},
                context,
                _definition(),
            )

    @pytest.mark.asyncio
    async def test_pair_without_separator_yields_empty_value(self, context: StepContext) -> None:
        output = await ParseKvStep().invoke({"input": "flag;id=x"}, context, _definition())
        assert output.value == {"flag": "", "id": "x"}

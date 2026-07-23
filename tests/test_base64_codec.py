#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Tests for util/base64 — encode/decode with base64 and base64url."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinitionV2
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.utility.base64_codec import Base64Step

# A realistic AAS identifier: URLs contain '/' and '+' collisions that make the
# url_safe alphabet meaningful.
_AAS_ID = "https://example.com/aas/12345?x=1+2"
# Standard base64 of _AAS_ID contains '+' and '/'; url-safe swaps them.
_STD = "aHR0cHM6Ly9leGFtcGxlLmNvbS9hYXMvMTIzNDU/eD0xKzI="
_URLSAFE = "aHR0cHM6Ly9leGFtcGxlLmNvbS9hYXMvMTIzNDU_eD0xKzI="


@pytest.fixture()
def context() -> StepContext:
    return StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())


def _definition() -> StepDefinitionV2:
    return StepDefinitionV2(id="b64", uses="util/base64")


class TestBase64Step:
    @pytest.mark.asyncio
    async def test_encode_standard(self, context: StepContext) -> None:
        output = await Base64Step().execute(
            {"input": _AAS_ID}, context, _definition(),
        )
        assert output.value == _STD

    @pytest.mark.asyncio
    async def test_encode_url_safe(self, context: StepContext) -> None:
        output = await Base64Step().execute(
            {"input": _AAS_ID, "url_safe": True}, context, _definition(),
        )
        assert output.value == _URLSAFE
        assert "/" not in output.value
        assert "+" not in output.value

    @pytest.mark.asyncio
    async def test_decode_standard(self, context: StepContext) -> None:
        output = await Base64Step().execute(
            {"input": _STD, "mode": "decode"}, context, _definition(),
        )
        assert output.value == _AAS_ID

    @pytest.mark.asyncio
    async def test_decode_url_safe(self, context: StepContext) -> None:
        output = await Base64Step().execute(
            {"input": _URLSAFE, "mode": "decode", "url_safe": True},
            context,
            _definition(),
        )
        assert output.value == _AAS_ID

    @pytest.mark.asyncio
    async def test_encode_strip_padding_then_decode(self, context: StepContext) -> None:
        encoded = await Base64Step().execute(
            {"input": _AAS_ID, "url_safe": True, "strip_padding": True},
            context,
            _definition(),
        )
        assert not encoded.value.endswith("=")
        # Decode restores padding automatically.
        decoded = await Base64Step().execute(
            {"input": encoded.value, "mode": "decode", "url_safe": True},
            context,
            _definition(),
        )
        assert decoded.value == _AAS_ID

    @pytest.mark.asyncio
    async def test_round_trip_unicode(self, context: StepContext) -> None:
        text = "Bauteil-Ännderung — 車両"
        encoded = await Base64Step().execute({"input": text}, context, _definition())
        decoded = await Base64Step().execute(
            {"input": encoded.value, "mode": "decode"}, context, _definition(),
        )
        assert decoded.value == text

    @pytest.mark.asyncio
    async def test_stores_in_variable(self, context: StepContext) -> None:
        await Base64Step().execute(
            {"input": _AAS_ID, "url_safe": True, "store_in_variable": "aas_b64"},
            context,
            _definition(),
        )
        assert context.get_variable("aas_b64") == _URLSAFE

    @pytest.mark.asyncio
    async def test_missing_input_raises(self, context: StepContext) -> None:
        with pytest.raises(KeyError, match="requires an 'input'"):
            await Base64Step().execute({"mode": "encode"}, context, _definition())

    @pytest.mark.asyncio
    async def test_non_string_input_raises(self, context: StepContext) -> None:
        with pytest.raises(TypeError, match="expects a string input"):
            await Base64Step().execute({"input": 123}, context, _definition())

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="must be 'encode' or 'decode'"):
            await Base64Step().execute(
                {"input": _AAS_ID, "mode": "flip"}, context, _definition(),
            )

    @pytest.mark.asyncio
    async def test_decode_invalid_base64_raises(self, context: StepContext) -> None:
        with pytest.raises(ValueError, match="not valid base64"):
            await Base64Step().execute(
                {"input": "!!!not base64!!!", "mode": "decode"}, context, _definition(),
            )

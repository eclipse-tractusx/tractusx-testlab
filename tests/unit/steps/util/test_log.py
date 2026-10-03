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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""util/log writes to the host's Python loggers, so its line is masked first."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.logging.masking import forget_secrets, register_secret
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.util.log import LogStep

_SECRET = "SECRET-ENV-VALUE-123"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    yield
    forget_secrets()


@pytest.mark.asyncio
async def test_the_logged_line_is_masked_and_the_output_is_not(
    caplog: pytest.LogCaptureFixture,
) -> None:
    register_secret(_SECRET, run="run-1")
    context = StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())

    with caplog.at_level(logging.INFO, logger="tractusx_testlab.steps.util.log"):
        output = await LogStep().invoke(
            {"value": {"pw": _SECRET, "client_secret": "short", "n": 1}, "message": _SECRET},
            context,
            StepDefinition(id="dump", uses="util/log"),
        )

    assert caplog.records
    assert all(_SECRET not in record.getMessage() for record in caplog.records)
    assert all("short" not in record.getMessage() for record in caplog.records)
    assert output.value == {"pw": _SECRET, "client_secret": "short", "n": 1}

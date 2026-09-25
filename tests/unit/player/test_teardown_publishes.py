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

"""A teardown step reads what an earlier teardown step published.

The compiler has always accepted ``${{ teardown.<id>.<field> }}``, and the
phase runner did not publish teardown outputs, so every such reference failed
at run time as unresolved — a find-then-delete teardown could not work.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition, StepStatus
from tractusx_testlab.player.execution.phase import TEARDOWN, run_phase


@pytest.mark.asyncio
async def test_a_teardown_step_reads_an_earlier_teardown_output(mock_context: MagicMock) -> None:
    test = MagicMock()
    test.definition.id = "t"
    test.dataspace_version = None
    test.definition.teardown = [
        StepDefinition(
            id="first",
            uses="util/log",
            with_={"message": "m", "value": "found-id"},
            returns={"value": {"type": "string"}},
        ),
        StepDefinition(
            id="second",
            uses="util/log",
            with_={"message": "m", "value": "${{ teardown.first.value }}"},
        ),
    ]

    results, _ = await run_phase(test, mock_context, "job-1", MagicMock(), None, TEARDOWN)

    assert [result.status for result in results] == [StepStatus.PASSED, StepStatus.PASSED]
    assert results[1].output == "found-id"

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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Reading a connector's state cannot hang the run.

The negotiation poll loop read the management API inline, so the blocking
``requests`` call the SDK makes — which carries no timeout — ran on the event
loop. A connector that accepted the connection and then answered nothing froze
the loop, and a frozen loop runs no timers: neither the step's own deadline nor
the callback server the SUT is talking to. That is how a negotiation which was
not working consumed a whole CI job instead of failing in a minute.

These pin both halves of the fix: the read is bounded, and the loop stays free
while it waits.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepExecutionError
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.connector.negotiate import NegotiateStep

_NEGOTIATION_ID = "neg-001"


class _Response:
    """The bare shape of the ``requests.Response`` a controller hands back."""

    def __init__(self, body: dict) -> None:
        self.status_code = 200
        self._body = body

    def json(self) -> Any:
        return self._body


class _SilentController:
    """A controller that accepts the read and then never answers it."""

    def __init__(self, release: threading.Event) -> None:
        self.release = release

    def get_by_id(self, oid: str, **kwargs: Any) -> _Response:
        self.release.wait()
        return _Response({"@id": oid, "state": "FINALIZED"})


@pytest.fixture()
def silent_consumer(mock_context: MagicMock) -> tuple[threading.Event, MagicMock]:
    """A consumer whose negotiation controller never answers a read."""
    release = threading.Event()
    consumer = MagicMock()
    consumer.contract_negotiations = _SilentController(release)
    consumer.start_edr_negotiation.return_value = _NEGOTIATION_ID
    mock_context.dataspace.consumer.return_value = consumer
    return release, consumer


class TestASilentConnectorDoesNotHangTheRun:
    async def test_a_state_read_that_never_answers_fails_the_step(
        self,
        mock_context: MagicMock,
        silent_consumer: tuple[threading.Event, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sdk_call, "DEFAULT_SDK_TIMEOUT", 0.05)
        release, _ = silent_consumer

        try:
            with pytest.raises(StepExecutionError, match="did not answer within"):
                await NegotiateStep().invoke({}, mock_context, MagicMock())
        finally:
            release.set()

    async def test_the_loop_keeps_serving_while_the_connector_is_silent(
        self,
        mock_context: MagicMock,
        silent_consumer: tuple[threading.Event, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Whatever else the run has to do — answer a callback — still happens."""
        monkeypatch.setattr(sdk_call, "DEFAULT_SDK_TIMEOUT", 0.05)
        release, _ = silent_consumer
        served = False

        async def other_work() -> None:
            nonlocal served
            served = True

        try:
            with pytest.raises(StepExecutionError):
                await asyncio.gather(
                    NegotiateStep().invoke({}, mock_context, MagicMock()), other_work()
                )
        finally:
            release.set()

        assert served, "the event loop was blocked by the connector read"

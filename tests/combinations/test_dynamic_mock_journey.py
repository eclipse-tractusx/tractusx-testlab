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

"""``labs/mock/api/dynamic`` — a mock whose reply depends on the call.

The server is the real one on a real port, and the SUT calls it from another
thread, as in ``test_callback_journey``: the mock's steps run on the test's
event loop while the call arrives on uvicorn's, and that hand-over is most of
what can go wrong. A call is therefore always made with ``call_soon`` while
the test awaits the wait step — a blocking call from the test's own thread
would hold the loop the mock's steps have to run on.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from combinations.harness import Harness, build_context
from combinations.mock_server_double import MockServer
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

pytestmark = pytest.mark.asyncio

_REQUEST = {
    "header": {
        "messageId": "urn:uuid:request-1",
        "senderBpn": "BPNL000000000001",
        "receiverBpn": "BPNL000000000002",
    },
    "content": {"certificateType": "iso9001"},
}


@pytest.fixture()
def server() -> Generator[MockServer, None, None]:
    clear_mocks()
    clear_callback_manager()
    running = MockServer().start()
    try:
        yield running
    finally:
        running.stop()
        clear_mocks()
        clear_callback_manager()


@pytest.fixture()
def harness(server: MockServer) -> Harness:
    return Harness(build_context(config=server.config))


def _dynamic(process: list[dict], **reply: Any) -> dict:
    return {
        "id": "endpoint",
        "uses": "labs/mock/api/dynamic",
        "with": {"path": "/companycertificate/request", "process": process, **reply},
        "returns": {"mock": {"type": "object"}, "full_mock_url": {"type": "string"}},
    }


def _keep(step_id: str, value: Any, kind: str = "object") -> dict:
    """Hold *value* under *step_id* — published, as every step's, only via ``returns:``."""
    return {
        "id": step_id,
        "uses": "util/log",
        "with": {"value": value},
        "returns": {"value": {"type": kind}},
    }


def _answer_by_type() -> dict:
    """COMPLETED for a type the mock holds, REJECTED otherwise — one id either way."""
    return {
        "id": "pick",
        "uses": "flow/if",
        "with": {
            "conditions": [
                {
                    "input": "${{ *.request.body }}",
                    "path": "content.certificateType",
                    "operator": "one_of",
                    "value": ["iso9001", "iatf16949"],
                }
            ],
            "then": [_keep("verdict", {"requestStatus": "COMPLETED"})],
            "else": [_keep("verdict", {"requestStatus": "REJECTED"})],
        },
    }


_WAIT = {
    "id": "await_call",
    "uses": "mock/wait/http_request",
    "with": {"mock": "${{ execution.endpoint.mock }}", "timeout_s": 5},
    "returns": {"request_body": {"type": "object"}},
}


async def _answer(harness: Harness, server: MockServer, step: dict, body: Any) -> Any:
    """Open the mock, have the SUT call it, and hand back the reply it got."""
    opened = await harness.run(step)
    assert opened.passed, [(r.step_name, r.error) for r in opened.failures]
    call = server.call_soon(opened.variables["full_mock_url"], json=body)
    waited = await harness.run(_WAIT)
    assert waited.passed, [(r.step_name, r.error) for r in waited.failures]
    return call.wait()


class TestTheReplyIsWorkedOutPerCall:
    async def test_the_reply_echoes_and_swaps_the_request_header(
        self, harness: Harness, server: MockServer
    ) -> None:
        step = _dynamic(
            [],
            response_body={
                "header": {
                    "relatedMessageId": "${{ *.request.body.header.messageId }}",
                    "senderBpn": "${{ *.request.body.header.receiverBpn }}",
                    "receiverBpn": "${{ *.request.body.header.senderBpn }}",
                }
            },
        )

        reply = await _answer(harness, server, step, _REQUEST)

        assert reply.json() == {
            "header": {
                "relatedMessageId": "urn:uuid:request-1",
                "senderBpn": "BPNL000000000002",
                "receiverBpn": "BPNL000000000001",
            }
        }

    async def test_a_flow_if_branch_decides_the_body(
        self, harness: Harness, server: MockServer
    ) -> None:
        step = _dynamic([_answer_by_type()], response_body="${{ *.process.verdict.value }}")

        reply = await _answer(harness, server, step, _REQUEST)

        assert reply.json() == {"requestStatus": "COMPLETED"}

    async def test_the_other_branch_answers_the_other_call(
        self, harness: Harness, server: MockServer
    ) -> None:
        step = _dynamic([_answer_by_type()], response_body="${{ *.process.verdict.value }}")
        unknown = {**_REQUEST, "content": {"certificateType": "iso14001"}}

        reply = await _answer(harness, server, step, unknown)

        assert reply.json() == {"requestStatus": "REJECTED"}

    async def test_the_status_can_come_from_a_step(
        self, harness: Harness, server: MockServer
    ) -> None:
        step = _dynamic(
            [_keep("status", 202, "integer")], response_status="${{ *.process.status.value }}"
        )

        reply = await _answer(harness, server, step, _REQUEST)

        assert reply.status_code == 202

    async def test_a_reply_mixes_what_the_test_knows_with_the_call(
        self, harness: Harness, server: MockServer
    ) -> None:
        harness.seed(**{"setup.certificate.value": "doc-7"})
        step = _dynamic(
            [_keep("id", "fresh", "string")],
            response_body={
                "documentId": "${{ setup.certificate.value }}",
                "messageId": "urn:uuid:${{ *.process.id.value }}",
            },
        )

        reply = await _answer(harness, server, step, _REQUEST)

        assert reply.json() == {"documentId": "doc-7", "messageId": "urn:uuid:fresh"}


class TestACallStaysItsOwn:
    async def test_what_the_steps_publish_never_reaches_the_run(
        self, harness: Harness, server: MockServer
    ) -> None:
        step = _dynamic([_answer_by_type()], response_body="${{ *.process.verdict.value }}")

        await _answer(harness, server, step, _REQUEST)

        leaked = [name for name in harness.context.variables if name.startswith("*.")]
        assert leaked == []

    async def test_the_wait_still_receives_the_call(
        self, harness: Harness, server: MockServer
    ) -> None:
        opened = await harness.run(_dynamic([], response_body={}))
        server.call_soon(opened.variables["full_mock_url"], json=_REQUEST)

        waited = await harness.run(_WAIT)

        assert waited.variables["request_body"] == _REQUEST


class TestWhenNoReplyCanBeWorkedOut:
    async def test_a_failing_step_answers_500_without_saying_why(
        self, harness: Harness, server: MockServer
    ) -> None:
        failing = {
            "id": "check",
            "uses": "util/log",
            "with": {"value": "${{ *.request.body.header.messageId }}"},
            "validate": [
                {"uses": "validate/assert", "with": {"input": "value", "operator": "is_null"}}
            ],
        }

        reply = await _answer(harness, server, _dynamic([failing]), _REQUEST)

        assert reply.status_code == 500
        assert "check" not in reply.text

    async def test_a_reference_to_nothing_answers_500(
        self, harness: Harness, server: MockServer
    ) -> None:
        step = _dynamic([], response_body="${{ *.request.body.header.missing }}")

        reply = await _answer(harness, server, step, _REQUEST)

        assert reply.status_code == 500

    async def test_steps_slower_than_the_timeout_answer_500(
        self, harness: Harness, server: MockServer
    ) -> None:
        slow = {"uses": "flow/delay", "with": {"seconds": 2}}

        reply = await _answer(harness, server, _dynamic([slow], process_timeout=0.2), _REQUEST)

        assert reply.status_code == 500

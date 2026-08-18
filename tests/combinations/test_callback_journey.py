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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""``mock/api`` and ``mock/wait/http_request`` — the inbound half of a TCK.

Every other step in the catalogue makes a call and reads the answer. This pair
inverts that: the script hands the system under test an address, the SUT calls
it whenever it is ready, and the script blocks until it does. That is the shape
of every asynchronous Catena-X flow — a notification, a certificate callback,
an EDR push.

Three things have to line up and none of them show in either step's contract:
the URL handed out has to be one the server actually routes, the request has to
resolve the listener the script is waiting on, and the future being resolved
belongs to the script's event loop while the request arrives on uvicorn's. So
the server here is the real one, on a real port, and the SUT is a real client
on another thread.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest

from combinations.harness import Harness, build_context
from combinations.mock_server_double import MockServer
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def server() -> Generator[MockServer, None, None]:
    """A running TestLab server, with the module state it uses reset around it.

    The mock routes and the callback manager are both module-level, and the
    manager's futures belong to the loop that created them. Left in place, one
    test's leftovers resolve the next test's wait with the wrong payload — or
    with a future from a loop that has since closed.
    """
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
def sut_harness(server: MockServer) -> Harness:
    """A harness whose config points the steps at the running server."""
    return Harness(build_context(config=server.config))


def _endpoint(path: str, status: int = 202, body: object = None) -> dict:
    """Register a callback address, the way a TCK opens an async flow."""
    return {
        "id": "endpoint",
        "uses": "mock/api",
        "with": {
            "path": path,
            "method": "POST",
            "response_status": status,
            "response_body": body if body is not None else {"ack": True},
        },
        "returns": {
            "mock": {"type": "object"},
            "full_mock_url": {"type": "string"},
        },
    }


def _wait(timeout_s: float = 5.0) -> dict:
    """Block until the SUT calls it, reading the mock the first step returned."""
    return {
        "id": "await_call",
        "uses": "mock/wait/http_request",
        "with": {"mock": "${{ execution.endpoint.mock }}", "timeout_s": timeout_s},
        "returns": {
            "request_body": {"type": "object"},
            "request_method": {"type": "string"},
            "request_path": {"type": "string"},
            "request_query_params": {"type": "object"},
        },
    }


class TestThePairWorks:
    """The whole point: hand out an address, block, receive the call."""

    async def test_the_wait_unblocks_when_the_sut_calls(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        opened = await sut_harness.run(_endpoint("/certificate/request"))
        server.call_soon(opened.variables["full_mock_url"], json={"cert": "ISO9001"})

        outcome = await sut_harness.run(_wait())

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert outcome.variables["request_body"] == {"cert": "ISO9001"}

    async def test_the_url_handed_out_is_one_the_server_routes(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        """The failure this guards against is a 404 the script never sees."""
        opened = await sut_harness.run(_endpoint("/certificate/request"))

        response = server.call(opened.variables["full_mock_url"], json={"cert": "ISO9001"})

        assert response.status_code == 202

    async def test_the_sut_receives_the_canned_response(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        opened = await sut_harness.run(
            _endpoint("/certificate/request", status=201, body={"id": "cert-1"})
        )
        call = server.call_soon(opened.variables["full_mock_url"], json={})

        await sut_harness.run(_wait())

        response = call.wait()
        assert response.status_code == 201
        assert response.json() == {"id": "cert-1"}

    async def test_the_whole_request_is_readable_afterwards(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        """Method, path, query and body — everything a check might assert on."""
        opened = await sut_harness.run(_endpoint("/certificate/request"))
        server.call_soon(
            opened.variables["full_mock_url"],
            json={"cert": "ISO9001"},
            params={"trace": "abc"},
        )

        outcome = await sut_harness.run(_wait())

        assert outcome.variables["request_method"] == "POST"
        assert outcome.variables["request_path"] == "/certificate/request"
        assert outcome.variables["request_query_params"] == {"trace": "abc"}
        assert outcome.variables["request_body"] == {"cert": "ISO9001"}


class TestTheOrderTheyHappenIn:
    """The SUT does not wait for the script to be ready, so neither can this."""

    async def test_a_call_that_arrives_before_the_wait_starts_is_not_lost(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        """``mock/api`` registers the listener, which is what makes this safe.

        A fast SUT answers before the script reaches its wait step. Were the
        listener only created by the wait, the call would land on nothing and
        the script would then block for the full timeout waiting for a call
        that already happened.
        """
        opened = await sut_harness.run(_endpoint("/certificate/request"))
        server.call(opened.variables["full_mock_url"], json={"cert": "early"})

        outcome = await sut_harness.run(_wait(timeout_s=2))

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert outcome.variables["request_body"] == {"cert": "early"}

    async def test_two_endpoints_are_waited_on_independently(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        opened = await sut_harness.run(
            {
                "id": "request_ep",
                "uses": "mock/api",
                "with": {"path": "/certificate/request", "response_body": {"n": 1}},
                "returns": {"mock": {"type": "object"}, "full_mock_url": {"type": "string"}},
            },
            {
                "id": "status_ep",
                "uses": "mock/api",
                "with": {"path": "/certificate/status", "response_body": {"n": 2}},
                "returns": {"mock": {"type": "object"}, "full_mock_url": {"type": "string"}},
            },
        )
        server.call(opened.variables["execution.status_ep.full_mock_url"], json={"on": "status"})

        outcome = await sut_harness.run(
            {
                "id": "await_status",
                "uses": "mock/wait/http_request",
                "with": {
                    "mock": "${{ execution.status_ep.mock }}",
                    "timeout_s": 2,
                },
                "returns": {"request_path": {"type": "string"}},
            },
        )

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert outcome.variables["request_path"] == "/certificate/status"


class TestWhenNothingCalls:
    """A SUT that never calls back is the failure this pair exists to report."""

    async def test_the_wait_times_out_and_says_what_it_waited_for(
        self, sut_harness: Harness
    ) -> None:
        await sut_harness.run(_endpoint("/certificate/request"))

        outcome = await sut_harness.run(_wait(timeout_s=0.3))

        assert not outcome.passed
        error = outcome.error("await_call") or ""
        assert "Timed out" in error
        assert "/certificate/request" in error

    async def test_an_unregistered_path_is_refused_rather_than_swallowed(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        """A SUT calling the wrong address gets a 404, not a silent 200."""
        await sut_harness.run(_endpoint("/certificate/request"))

        response = server.call(f"http://127.0.0.1:{server.port}/certificate/typo", json={})

        assert response.status_code == 404


class TestTheCallbackDrivesTheRestOfTheScript:
    """What arrives is an ordinary step output — assertable, and readable on."""

    async def test_the_inbound_body_can_be_asserted_on_where_it_lands(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        opened = await sut_harness.run(_endpoint("/certificate/request"))
        server.call_soon(
            opened.variables["full_mock_url"],
            json={"cert": "ISO9001", "state": "RECEIVED"},
        )

        outcome = await sut_harness.run(
            {
                "id": "await_call",
                "uses": "mock/wait/http_request",
                "with": {
                    "mock": "${{ execution.endpoint.mock }}",
                    "timeout_s": 5,
                },
                "returns": {"request_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/field/equals",
                        "with": {
                            "input": "request_body",
                            "path": "state",
                            "value": "RECEIVED",
                        },
                    },
                    {
                        "uses": "validate/field/one_of",
                        "with": {
                            "input": "request_body",
                            "path": "cert",
                            "value": ["ISO9001", "ISO14001"],
                        },
                    },
                ],
            }
        )

        assert outcome.passed, outcome.assertion_messages("await_call")

    async def test_a_later_step_reads_the_inbound_body(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        opened = await sut_harness.run(_endpoint("/certificate/request"))
        server.call_soon(opened.variables["full_mock_url"], json={"cert": "ISO9001"})

        outcome = await sut_harness.run(
            _wait(),
            {
                "id": "cert_type",
                "uses": "util/json_path_extract",
                "with": {
                    "input": "${{ execution.await_call.request_body }}",
                    "path": "cert",
                },
            },
        )

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert outcome.output("cert_type") == "ISO9001"

    async def test_the_canned_response_can_carry_a_value_from_the_run(
        self, sut_harness: Harness, server: MockServer
    ) -> None:
        """A response body carries a value from the run, written the usual way.

        It used to be spelled ``@agreed_id`` and resolved by a second pass
        inside the mock step — the last surviving ``@name`` resolver, kept alive
        by this test alone. It also treated any JSON-LD value beginning with
        ``@`` as a variable reference on its way past. The body is a step
        parameter, so ``${{ ... }}`` in it is already resolved before the step
        runs, like every other parameter.
        """
        sut_harness.seed(agreed_id="agr-77")
        opened = await sut_harness.run(
            {
                "id": "endpoint",
                "uses": "mock/api",
                "with": {
                    "path": "/certificate/request",
                    "response_body": {"agreementId": "${{ env.agreed_id }}"},
                },
                "returns": {"full_mock_url": {"type": "string"}},
            }
        )

        response = server.call(opened.variables["full_mock_url"], json={})

        assert response.json() == {"agreementId": "agr-77"}


class TestWithoutTheServer:
    """Neither step is usable on its own, and the failure says which is missing."""

    async def test_waiting_without_a_server_is_a_named_failure(self, harness: Harness) -> None:
        """The plain ``harness`` fixture has no server behind it.

        ``mock/api`` still registers — the registry is module state — so the
        script gets a URL that nothing serves. The wait is where that surfaces,
        and it names the missing piece rather than timing out on it.
        """
        clear_callback_manager()
        try:
            opened = await harness.run(_endpoint("/certificate/orphan"))
            outcome = await harness.run(_wait(timeout_s=0.2))
        finally:
            clear_mocks()

        assert opened.passed
        assert not outcome.passed
        assert "CallbackManager" in (outcome.error("await_call") or "")

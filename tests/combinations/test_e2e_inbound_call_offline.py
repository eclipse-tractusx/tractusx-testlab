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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The inbound e2e scenario, executed here — with a data plane that fetches.

``tests/e2e/connector-dtr-smoke/tests/inbound_call.yaml`` is the one scenario
where the dataspace calls testlab: the SUT's data plane fetches an asset from a
``mock/api`` endpoint, and ``mock/wait/http_request`` reads the request it
made. What ``e2e-umbrella.yml`` settles is whether a real EDC does that from a
pod. What can be settled here is everything the scenario has to get right
before that matters, and two things in it are not like the other scenarios.
The asset's ``base_url`` is an operator input read *inside* an inline asset
document, and a reference that stopped resolving there would register an asset
whose backend is the literal text ``${{ env.… }}`` — which the data plane
would then fail to fetch, twenty minutes into a job. And the path is the
script's to choose: the asset points at the mock server's root with
``proxyPath`` on, and the pull names the mock's path, so the path has to travel
from the script through the data plane to the mock.

So the data plane here is not a canned route. It is a server that fetches
whatever ``base_url`` the provider double was given, with the caller's path
appended, and relays the answer — the way the EDC's ``HttpData`` source does
with ``proxyPath``. If the reference did not resolve, or the path did not
travel, the fetch fails and the scenario's own checks say so.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests
import yaml

from combinations.connector_double import ConsumerDouble, ProviderDouble, ServicesDouble
from combinations.harness import Harness, build_context
from combinations.mock_server_double import MockServer
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

pytestmark = pytest.mark.asyncio

_SCENARIO = Path("tests/e2e/connector-dtr-smoke/tests/inbound_call.yaml")
_ASSET_ID = "testlab-e2e-inbound-asset"
_BACKEND_PATH = "/testlab-e2e/backend"
_NOTIFICATION_PATH = "/testlab-e2e/notification"


def _phase(phase: str) -> list[dict]:
    """The steps of one phase, as the shipped file declares them."""
    document = yaml.safe_load(_SCENARIO.read_text(encoding="utf-8"))
    return document.get(phase) or []


def _steps(phase: str, *ids: str) -> list[dict]:
    """The named steps of a phase, in the order the file declares them."""
    return [step for step in _phase(phase) if step["id"] in ids]


class _FetchingDataplane:
    """A provider data plane that fetches from the asset's backend and relays.

    Every request it receives is answered by forwarding it — method, path and
    body — to the ``base_url`` of the asset the provider double registered
    last, exactly as the EDC's ``HttpData`` source does when the asset proxies
    all three. It is a separate server on its own thread, so
    the call the mock receives arrives from outside the awaiting coroutine —
    the arrangement the wait step exists for.
    """

    def __init__(self, provider: ProviderDouble) -> None:
        self._provider = provider
        self.fetched: list[tuple[str, str]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        dataplane = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_args: object) -> None:
                """Keep the pytest output about the tests."""

            def _proxy(self) -> None:
                asset = dataplane._provider.created[-1]
                backend = str(asset["base_url"]).rstrip("/") + self.path
                dataplane.fetched.append((self.command, backend))
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else None
                try:
                    upstream = requests.request(
                        self.command,
                        backend,
                        data=body,
                        headers={"Content-Type": self.headers.get("Content-Type", "")},
                        timeout=5,
                    )
                    status, payload = upstream.status_code, upstream.content
                except requests.RequestException as exc:
                    status = 502
                    payload = json.dumps({"error": f"backend unreachable: {exc}"}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = _proxy
            do_POST = _proxy

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self._thread.start()
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


@pytest.fixture()
def server() -> Generator[MockServer, None, None]:
    """The real testlab server, with its module-level state reset around it."""
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
def provider() -> ProviderDouble:
    return ProviderDouble()


@pytest.fixture()
def dataplane(provider: ProviderDouble) -> Generator[_FetchingDataplane, None, None]:
    fetching = _FetchingDataplane(provider)
    yield fetching
    fetching.stop()


@pytest.fixture()
def harness(server: MockServer, provider: ProviderDouble, dataplane: _FetchingDataplane) -> Harness:
    """The scenario's world: a consumer offering the asset, a data plane that fetches."""
    catalog = {
        "dcat:dataset": [
            {
                # A dataset's `@id` is the asset id — that is what the one-shot
                # flow reports as `asset_id`, and what the scenario asserts on.
                "@id": _ASSET_ID,
                "edc:id": _ASSET_ID,
                "dct:type": {"@id": "https://w3id.org/catenax/taxonomy#TestData"},
                "odrl:hasPolicy": [{"@id": "offer-1", "odrl:permission": []}],
            }
        ]
    }
    consumer = ConsumerDouble(catalog, dataplane.start())
    harness = Harness(
        build_context(services=ServicesDouble(consumer, provider), config=server.config)
    )
    harness.seed(
        **{
            "infrastructure.sut.connector.dsp_url": "http://provider.local/api/v1/dsp",
            "infrastructure.sut.connector.participant_id": "BPNL000000000001",
            "usage_policy": {"permission": []},
            # What the workflow passes with `--var`: the mock server's root as
            # the SUT reaches it. Here the SUT is on this machine.
            "mock_server_external_url": f"http://127.0.0.1:{server.port}",
        }
    )
    return harness


@pytest.fixture()
async def outcome(harness: Harness):
    """Setup as far as the doubles go, then the whole execution phase."""
    opened = await harness.run(
        *_steps("setup", "open_backend", "open_notification", "create_asset"), phase="setup"
    )
    assert opened.passed, [(r.step_name, r.error) for r in opened.failures]
    return await harness.run(*_phase("execution"))


class TestTheScenarioRuns:
    async def test_every_step_passes(self, outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    async def test_every_declared_check_was_evaluated(self, outcome) -> None:
        declared = sum(len(step.get("validate") or []) for step in _phase("execution"))
        assert sum(len(r.assertions) for r in outcome.results) == declared


class TestTheBackendIsTheMock:
    """The asset's backend is the mock server, at the address the operator gave."""

    async def test_the_asset_registered_carries_the_resolved_root(
        self, outcome, provider: ProviderDouble, server: MockServer
    ) -> None:
        """The reference inside the inline asset document resolved, and to the
        input — not to `full_mock_url`, which says `localhost`. The root alone:
        which endpoint is asked for is the pull's business, not the asset's."""
        assert provider.created[-1]["base_url"] == f"http://127.0.0.1:{server.port}"

    async def test_the_asset_lets_the_path_the_method_and_the_body_through(
        self, outcome, provider: ProviderDouble
    ) -> None:
        """The step passes `proxy_params` through as given, and the SDK's
        default is not applied to an explicit None — so a scenario that forgot
        this would register an asset the data plane fetches at its root."""
        assert provider.created[-1]["proxy_params"] == {
            "proxyPath": "true",
            "proxyMethod": "true",
            "proxyBody": "true",
        }

    async def test_the_data_plane_forwarded_both_calls_to_that_root(
        self, outcome, dataplane: _FetchingDataplane, server: MockServer
    ) -> None:
        root = f"http://127.0.0.1:{server.port}"
        assert dataplane.fetched == [
            ("GET", f"{root}{_BACKEND_PATH}"),
            ("POST", f"{root}{_NOTIFICATION_PATH}"),
        ]

    async def test_what_came_through_the_data_plane_is_the_mocks_answer(self, outcome) -> None:
        assert outcome.output("fetch_through_sut") == {"served_by": "testlab-mock", "answer": 42}


class TestTheWaitReadsTheDataPlanesRequest:
    async def test_the_request_read_back_is_the_one_the_data_plane_made(self, outcome) -> None:
        read = outcome.output("await_call")
        assert read["request_method"] == "GET"
        assert read["request_path"] == _BACKEND_PATH

    async def test_the_posted_payload_is_what_the_mock_received(self, outcome) -> None:
        """Field for field: what the script sent is what arrived, two hops later."""
        sent = next(s for s in _phase("execution") if s["id"] == "notify_through_sut")["with"][
            "body"
        ]
        assert outcome.output("await_notification")["request_body"] == sent
        assert outcome.output("await_notification")["request_method"] == "POST"

    async def test_the_call_that_arrived_before_the_wait_was_held_for_it(self, outcome) -> None:
        """The data plane called during `fetch_through_sut`; the wait came after.

        That order is what a real SUT forces, and the listener `mock/api`
        opened in setup is what keeps the call. A wait that had to be reached
        first would time out here, thirty seconds after the call it missed.
        """
        assert outcome.variables["elapsed_ms"] < 1000

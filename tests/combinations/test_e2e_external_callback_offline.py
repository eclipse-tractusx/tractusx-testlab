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

"""The external-callback e2e scenario, executed here — stub included.

``tests/e2e/connector-dtr-smoke/tests/external_callback.yaml`` is the scenario
where the test blocks on ``mock/wait/http_request`` and something else, from
its own process, calls the mock while it waits. In the cluster that something
is ``ci/stub_caller.py`` running as a pod. Here it is the same file, run as a
subprocess — a different process on this machine, which is the property the
scenario is about. The mock server is the real one on a free port, and the
test's steps are read out of the shipped YAML.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest
import requests
import yaml

from combinations.harness import Harness, build_context
from combinations.mock_server_double import MockServer, free_port
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

pytestmark = pytest.mark.asyncio

_SCENARIO = Path("tests/e2e/connector-dtr-smoke/tests/external_callback.yaml")
_STUB = Path("tests/e2e/connector-dtr-smoke/ci/stub_caller.py")
_CALLBACK_PATH = "/testlab-e2e/callback"


def _phase(phase: str) -> list[dict]:
    document = yaml.safe_load(_SCENARIO.read_text(encoding="utf-8"))
    return document.get(phase) or []


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
def stub() -> Generator[str, None, None]:
    """The shipped stub, as its own process, ready to be told what to call."""
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, str(_STUB), "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline:
            try:
                if requests.get(f"{base}/health", timeout=0.5).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.05)
        else:
            raise RuntimeError(f"stub caller did not come up on port {port}")
        yield base
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.fixture()
def harness(server: MockServer, stub: str) -> Harness:
    harness = Harness(build_context(config=server.config))
    harness.seed(
        **{
            "stub_caller_url": stub,
            "mock_server_external_url": f"http://127.0.0.1:{server.port}",
        }
    )
    return harness


@pytest.fixture()
async def outcome(harness: Harness):
    opened = await harness.run(*_phase("setup"), phase="setup")
    assert opened.passed, [(r.step_name, r.error) for r in opened.failures]
    return await harness.run(*_phase("execution"))


class TestTheScenarioRuns:
    async def test_every_step_passes(self, outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    async def test_every_declared_check_was_evaluated(self, outcome) -> None:
        declared = sum(len(step.get("validate") or []) for step in _phase("execution"))
        assert sum(len(r.assertions) for r in outcome.results) == declared


class TestTheWaitWaited:
    """The call arrived while the test was blocked, not before it got there."""

    async def test_the_wait_blocked_for_the_delay_the_stub_was_given(self, outcome) -> None:
        asked = _phase("execution")[0]["with"]["body"]["delay_s"]
        assert outcome.variables["elapsed_ms"] >= asked * 1000 - 500

    async def test_what_arrived_is_what_the_stub_was_told_to_send(self, outcome) -> None:
        told = _phase("execution")[0]["with"]["body"]
        assert outcome.variables["request_method"] == told["method"]
        assert outcome.variables["request_path"] == _CALLBACK_PATH
        assert outcome.variables["request_body"] == told["body"]

    async def test_the_stub_was_pointed_at_the_operators_address_not_localhost(
        self, server: MockServer
    ) -> None:
        """`full_mock_url` says `localhost`; the stub is told the external root."""
        told = _phase("execution")[0]["with"]["body"]["url"]
        assert told == "${{ env.mock_server_external_url }}" + _CALLBACK_PATH

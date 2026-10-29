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

"""The API steps e2e scenario, executed here — and its trace read by the workflow's own check.

``tests/e2e/connector-dtr-smoke/tests/api_steps.yaml`` calls the umbrella's
registry with the labs API steps, checks every answer against the registry's
own OpenAPI document, and the workflow then reads the trace back. Here the
scenario runs against a loopback registry that answers as DTR 0.11.0 does, a
data plane that refuses a call without the EDR token and relays one with it,
and connector doubles for the negotiations. The results are then written as a
trace and handed to the workflow's verifier, unchanged but for where it reads
— so a scenario edit that the verifier would reject fails here first. The
offer guard's separate run is mirrored the same way.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml

from combinations.connector_double import ConsumerDouble, ProviderDouble, ServicesDouble
from combinations.harness import Harness, Outcome, build_context
from combinations.http_double import HttpDouble
from tests.paths import REPO_ROOT
from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models import TckDefinition
from tractusx_testlab.openapi import forget_api_documents
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.player.execution._trace_publisher import TracePublisher

pytestmark = pytest.mark.asyncio

_TCK = Path("tests/e2e/connector-dtr-smoke")
_WORKFLOW = REPO_ROOT / ".github/workflows/e2e-umbrella.yml"
_ASSET_ID = "testlab-e2e-api-steps-dtr-asset"
_ABSENT = "dXJuOnV1aWQ6dGVzdGxhYi1lMmUtYWJzZW50"
_TOKEN = "Bearer edr"
#: What DTR 0.11.0's GetSelfDescription answers.
_PROFILES = [
    "https://admin-shell.io/aas/API/3/0/AssetAdministrationShellRegistryServiceSpecification/SSP-001",
    "https://admin-shell.io/aas/API/3/0/DiscoveryServiceSpecification/SSP-001",
    "https://admin-shell.io/aas/API/3/1/AssetAdministrationShellRegistryServiceSpecification/SSP-001",
    "https://admin-shell.io/aas/API/3/1/DiscoveryServiceSpecification/SSP-001",
]
_NOT_FOUND = {
    "messages": [
        {
            "messageType": "Error",
            "text": "Shell for identifier urn:uuid:testlab-e2e-absent not found",
            "timestamp": "2026-10-29T12:00:00.000Z",
        }
    ]
}


def _scenario(name: str) -> dict[str, Any]:
    return yaml.safe_load((_TCK / "tests" / name).read_text(encoding="utf-8"))


class _GuardedDataplane:
    """A data plane that refuses a call without the EDR token and relays one with it."""

    def __init__(self, backend: str) -> None:
        self._backend = backend
        self.relayed: list[str] = []
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> str:
        plane = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_args: object) -> None:
                """Keep the pytest output about the tests."""

            def do_GET(self) -> None:
                if self.headers.get("Authorization") != _TOKEN:
                    status, payload = 401, b'{"errors":["Request could not be authenticated"]}'
                else:
                    plane.relayed.append(self.path)
                    upstream = requests.get(plane._backend + self.path, timeout=5)
                    status, payload = upstream.status_code, upstream.content
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        ).start()
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


@pytest.fixture()
def registry() -> Generator[str, None, None]:
    double = (
        HttpDouble()
        .json_route("GET", "/api/v3/description", {"profiles": _PROFILES})
        .json_route("GET", f"/api/v3/shell-descriptors/{_ABSENT}", _NOT_FOUND, status=404)
    )
    url = double.start()
    try:
        yield url
    finally:
        double.stop()


@pytest.fixture()
def dataplane(registry: str) -> Generator[_GuardedDataplane, None, None]:
    plane = _GuardedDataplane(f"{registry}/api/v3")
    yield plane
    plane.stop()


def _harness(registry: str, dataplane_url: str) -> Harness:
    forget_api_documents()
    catalog = {
        "dcat:dataset": [
            {
                "@id": _ASSET_ID,
                "edc:id": _ASSET_ID,
                "dct:type": {"@id": "https://w3id.org/catenax/taxonomy#DigitalTwinRegistry"},
                "odrl:hasPolicy": [{"@id": "offer-1", "odrl:permission": []}],
            }
        ]
    }
    consumer = ConsumerDouble(catalog, dataplane_url, token=_TOKEN)
    context = build_context(services=ServicesDouble(consumer, ProviderDouble()))
    manifest = yaml.safe_load((_TCK / "index.yaml").read_text(encoding="utf-8"))
    seed_context_variables(
        context, Tck(TckDefinition.model_validate(manifest), base_dir=_TCK), None
    )
    harness = Harness(context)
    harness.seed(
        **{
            "infrastructure.sut.dtr.base_url": registry,
            "infrastructure.sut.connector.dsp_url": "http://provider.local/api/v1/dsp",
            "infrastructure.sut.connector.participant_id": "BPNL000000000001",
            "usage_policy": {"permission": []},
            "setup.create_dtr_asset.asset_id": _ASSET_ID,
        }
    )
    return harness


@pytest.fixture()
async def outcome(registry: str, dataplane: _GuardedDataplane) -> Outcome:
    return await _harness(registry, dataplane.start()).run(
        *_scenario("api_steps.yaml")["execution"]
    )


def _verifier(name: str, data_dir: Path) -> str:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    (step,) = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if step.get("name") == name
    ]
    opener = "poetry run python - <<'PY'\n"
    script = step["run"]
    assert script.startswith(opener) and script.endswith("PY\n")
    script = script[len(opener) : -len("PY\n")]
    assert script.count('pathlib.Path("/data")') == 1
    return script.replace('pathlib.Path("/data")', f"pathlib.Path({str(data_dir)!r})")


def _write(outcome: Outcome, test: str, path: Path) -> None:
    publisher = TracePublisher(ExecutionTrace("testlab-e2e-connector-dtr-smoke", path))
    publisher.run_started("offline-run", "testlab-e2e-connector-dtr-smoke")
    for result in outcome.results:
        publisher.step_ended(test, result.step_name, result)


def _verify(name: str, data_dir: Path) -> None:
    exec(compile(_verifier(name, data_dir), str(_WORKFLOW), "exec"), {"__name__": "__main__"})


class TestTheScenario:
    async def test_every_step_passes(self, outcome: Outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error, r.assertions) for r in outcome.failures]

    async def test_every_declared_check_was_evaluated(self, outcome: Outcome) -> None:
        execution = _scenario("api_steps.yaml")["execution"]
        declared = sum(len(step.get("validate") or []) for step in execution)
        # A check step's own verdicts are named; the scenario's validate: entries are not.
        own = sum(1 for r in outcome.results for a in r.assertions if a.assertion.name is None)
        assert own == declared

    async def test_the_tokenless_call_was_refused_by_the_data_plane(self, outcome: Outcome) -> None:
        assert outcome.output("dataplane_without_token")["status_code"] == 401
        check = outcome.result("dataplane_without_token").assertions[0]
        assert check.passed

    async def test_the_sweep_swept_both_operations(self, outcome: Outcome) -> None:
        rows = {
            r["operation"]: (r["verdict"], r["status"])
            for r in outcome.output("dtr_sweep")["results"]
        }
        assert rows == {
            "GetSelfDescription": ("passed", 200),
            "GetAssetAdministrationShellDescriptorById": ("passed", 404),
        }

    async def test_the_workflow_verifier_accepts_the_trace(
        self, outcome: Outcome, tmp_path: Path
    ) -> None:
        _write(outcome, "api-steps", tmp_path / "run.jsonl")
        _verify("Verify the API steps in the execution trace", tmp_path)

    async def test_the_workflow_verifier_rejects_a_failed_check(
        self, outcome: Outcome, tmp_path: Path
    ) -> None:
        broken = outcome.result("dtr_description")
        broken.assertions[0] = broken.assertions[0].model_copy(update={"passed": False})
        _write(outcome, "api-steps", tmp_path / "run.jsonl")
        with pytest.raises(SystemExit, match="dtr_description"):
            _verify("Verify the API steps in the execution trace", tmp_path)

    async def test_the_workflow_verifier_rejects_a_missing_step(
        self, outcome: Outcome, tmp_path: Path
    ) -> None:
        outcome.results[:] = [r for r in outcome.results if r.step_name != "dtr_sweep"]
        _write(outcome, "api-steps", tmp_path / "run.jsonl")
        with pytest.raises(SystemExit, match="dtr_sweep ended 0 times"):
            _verify("Verify the API steps in the execution trace", tmp_path)


class TestTheOfferGuard:
    async def test_the_unfiltered_pull_is_refused_and_the_verifier_reads_why(
        self, registry: str, dataplane: _GuardedDataplane, tmp_path: Path
    ) -> None:
        harness = _harness(registry, dataplane.start())
        outcome = await harness.run(*_scenario("offer_guard.yaml")["execution"])
        (result,) = outcome.results
        assert result.error_code == "OFFER_FILTER_MISSING"
        _write(outcome, "offer-guard", tmp_path / "run.jsonl")
        _verify("Verify the offer guard's refusal in the execution trace", tmp_path)

    async def test_the_verifier_rejects_a_guard_that_let_it_through(
        self, registry: str, dataplane: _GuardedDataplane, tmp_path: Path
    ) -> None:
        harness = _harness(registry, dataplane.start())
        step = {**_scenario("offer_guard.yaml")["execution"][0]}
        step["with"] = {**step["with"], "allow_any_offer": True}
        outcome = await harness.run(step)
        _write(outcome, "offer-guard", tmp_path / "run.jsonl")
        with pytest.raises(SystemExit, match="failed 0 times"):
            _verify("Verify the offer guard's refusal in the execution trace", tmp_path)


def test_the_full_suite_skips_the_test_meant_to_fail() -> None:
    workflow = _WORKFLOW.read_text(encoding="utf-8")
    assert '--var "skip_tests=offer_guard.yaml"' in workflow
    assert json.dumps("offer_guard.yaml") in json.dumps(
        [e["id"] for e in yaml.safe_load((_TCK / "index.yaml").read_text())["tests"]]
    )

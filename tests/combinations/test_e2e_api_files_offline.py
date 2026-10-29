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


"""`api_files.yaml`, the e2e scenario for `env.apis` (ADR-0030), run here.

Everything in it but one call is reachable without a cluster: the two API
files are the shipped ones, seeded by the player's own seeder from the shipped
manifest; the echo mock is the real mock server. The one call that needs the
umbrella — the deployed registry's `GET /api/v3/description` — is answered by a
loopback double with what Digital Twin Registry 0.11.0 answers
(`AssetAdministrationShellApiDelegate.getSelfDescription`).

What the cluster cannot cheaply show is also asserted here: the run records an
API document by its summary, so a step handed the 74 KiB registry document
writes a few hundred bytes, not the document.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import yaml

from combinations.harness import Harness, build_context
from combinations.http_double import HttpDouble
from combinations.mock_server_double import MockServer
from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.logging import wire
from tractusx_testlab.models import TckDefinition
from tractusx_testlab.openapi import forget_api_documents
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

_TCK = Path("tests/e2e/connector-dtr-smoke")
_SCENARIO = _TCK / "tests" / "api_files.yaml"

#: What DTR 0.11.0's GetSelfDescription answers.
_DTR_PROFILES = [
    "https://admin-shell.io/aas/API/3/0/AssetAdministrationShellRegistryServiceSpecification/SSP-001",
    "https://admin-shell.io/aas/API/3/0/DiscoveryServiceSpecification/SSP-001",
    "https://admin-shell.io/aas/API/3/1/AssetAdministrationShellRegistryServiceSpecification/SSP-001",
    "https://admin-shell.io/aas/API/3/1/DiscoveryServiceSpecification/SSP-001",
]


def _phase(phase: str) -> list[dict[str, Any]]:
    return yaml.safe_load(_SCENARIO.read_text(encoding="utf-8")).get(phase) or []


def _manifest() -> dict[str, Any]:
    return yaml.safe_load((_TCK / "index.yaml").read_text(encoding="utf-8"))


class TestTheManifest:
    def test_both_api_files_compile_one_typed_one_inferred(self, tmp_path: Path) -> None:
        forget_api_documents()
        _, execution = Compiler().compile_plain(_TCK / "index.yaml", tmp_path / "out")
        assert execution["apis"] == {
            "dtr": {
                "asset_key": "aas-registry-openapi.yaml",
                "type": "application/vnd.oai.openapi",
            },
            "testlab_mock": {
                "asset_key": "testlab-mock.json",
                "type": "application/vnd.oai.openapi+json",
            },
        }
        assert (tmp_path / "out" / "assets" / "apis" / "aas-registry-openapi.yaml").is_file()


class TestApiFiles:
    @pytest.fixture()
    def server(self) -> Generator[MockServer, None, None]:
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
    def registry(self) -> Generator[tuple[HttpDouble, str], None, None]:
        double = HttpDouble().json_route("GET", "/api/v3/description", {"profiles": _DTR_PROFILES})
        url = double.start()
        try:
            yield double, url
        finally:
            double.stop()

    @pytest.fixture()
    async def outcome(self, server: MockServer, registry: tuple[HttpDouble, str]):
        context = build_context(config=server.config)
        tck = Tck(TckDefinition.model_validate(_manifest()), base_dir=_TCK)
        seed_context_variables(context, tck, None)
        context.set_variable("infrastructure.sut.dtr.base_url", registry[1])
        harness = Harness(context)
        opened = await harness.run(*_phase("setup"), phase="setup")
        assert opened.passed, [(r.step_name, r.error) for r in opened.failures]
        return await harness.run(*_phase("execution"))

    @pytest.mark.asyncio
    async def test_every_step_passes(self, outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    @pytest.mark.asyncio
    async def test_every_declared_check_was_evaluated(self, outcome) -> None:
        declared = sum(len(step.get("validate") or []) for step in _phase("execution"))
        assert sum(len(r.assertions) for r in outcome.results) == declared

    @pytest.mark.asyncio
    async def test_the_registry_was_asked_for_its_description(
        self, outcome, registry: tuple[HttpDouble, str]
    ) -> None:
        assert [request.path for request in registry[0].received] == ["/api/v3/description"]

    @pytest.mark.parametrize("step_id", ["dtr_profile", "mock_key_header"])
    @pytest.mark.asyncio
    async def test_a_document_is_recorded_by_its_summary(self, outcome, step_id: str) -> None:
        record = wire.written(wire.as_recorded(outcome.result(step_id)).model_dump(mode="json"))
        summary = record["inputs"]["input"]["api_document"]
        assert set(summary) == {"openapi", "title", "version", "sha256"}
        assert len(json.dumps(record)) < 2_000

    @pytest.mark.asyncio
    async def test_the_registry_document_is_in_no_record(self, outcome) -> None:
        written = json.dumps(
            [wire.written(wire.as_recorded(r).model_dump(mode="json")) for r in outcome.results]
        )
        assert "x-semanticIds" not in written
        assert "ServiceDescription" not in written

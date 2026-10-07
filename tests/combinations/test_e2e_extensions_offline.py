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
## It was reviewed and tested by a human committer.


"""The experimental-extensions e2e scenario, executed here — before the cluster is.

``tests/e2e/connector-dtr-smoke/tests/experimental_extensions.yaml`` runs the
extensions the e2e manifest enables against the live dataspace, and the
workflow reads the result back from the trace. What can be settled without a
dataspace is settled here: the ``retry_on`` keys reach the extension rather
than the step, the retry really makes a second call through a data plane that
fetches, ``cac:`` reaches the step result — and the manifest needs its
``extensions:`` line, which the compiler would otherwise refuse twenty minutes
into a job.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

from combinations.connector_double import ConsumerDouble, ProviderDouble, ServicesDouble
from combinations.harness import Harness, build_context
from combinations.mock_server_double import MockServer
from combinations.test_e2e_inbound_call_offline import _FetchingDataplane
from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.models import TckDefinition
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

_TCK = Path("tests/e2e/connector-dtr-smoke")
_SCENARIO = _TCK / "tests" / "experimental_extensions.yaml"
_ASSET_ID = "testlab-e2e-extensions-asset"
_PATH = "/testlab-e2e/extensions"


def _phase(phase: str) -> list[dict]:
    document = yaml.safe_load(_SCENARIO.read_text(encoding="utf-8"))
    return document.get(phase) or []


def _steps(phase: str, *ids: str) -> list[dict]:
    return [step for step in _phase(phase) if step["id"] in ids]


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
def provider() -> ProviderDouble:
    return ProviderDouble()


@pytest.fixture()
def dataplane(provider: ProviderDouble) -> Generator[_FetchingDataplane, None, None]:
    fetching = _FetchingDataplane(provider)
    yield fetching
    fetching.stop()


@pytest.fixture()
def harness(server: MockServer, provider: ProviderDouble, dataplane: _FetchingDataplane) -> Harness:
    catalog = {
        "dcat:dataset": [
            {
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
            "mock_server_external_url": f"http://127.0.0.1:{server.port}",
        }
    )
    return harness


@pytest.fixture()
async def outcome(harness: Harness):
    opened = await harness.run(*_steps("setup", "open_backend", "create_asset"), phase="setup")
    assert opened.passed, [(r.step_name, r.error) for r in opened.failures]
    return await harness.run(*_phase("execution"))


class TestTheScenarioRuns:
    async def test_every_step_passes(self, outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    async def test_every_declared_check_was_evaluated(self, outcome) -> None:
        declared = sum(len(step.get("validate") or []) for step in _phase("execution"))
        assert sum(len(r.assertions) for r in outcome.results) == declared


class TestTheLabsRetryParameter:
    async def test_the_data_plane_was_called_twice_for_one_step(
        self, outcome, dataplane: _FetchingDataplane, server: MockServer
    ) -> None:
        """What the workflow counts in the trace: two calls, both to the mock's path."""
        root = f"http://127.0.0.1:{server.port}"
        assert dataplane.fetched == [("GET", f"{root}{_PATH}"), ("GET", f"{root}{_PATH}")]

    async def test_both_calls_are_recorded_on_the_step(self, outcome) -> None:
        assert len(outcome.result("fetch_with_retry").exchanges) == 2

    async def test_the_step_itself_was_never_given_the_keys(self, outcome) -> None:
        """It rejects unknown keys, so passing means they were taken out first."""
        assert outcome.result("fetch_with_retry").status.value == "PASSED"

    async def test_the_answer_is_the_mocks(self, outcome) -> None:
        assert outcome.output("fetch_with_retry") == {
            "served_by": "testlab-mock",
            "extension": "labs",
        }


class TestTheCacReferences:
    async def test_the_step_result_names_its_cac(self, outcome) -> None:
        assert outcome.result("pull_data").cac == ["TESTLAB-INTERNAL:v1.0.0:EXT-CAC-01"]

    async def test_the_check_with_its_own_keeps_it(self, outcome) -> None:
        checks = outcome.result("pull_data").assertions
        assert [check.assertion.cac for check in checks] == [
            None,
            ["TESTLAB-INTERNAL:v1.0.0:EXT-CAC-02"],
        ]


class TestTheManifestHasToEnableThem:
    def _errors(self, extensions: list[str]) -> list:
        manifest = yaml.safe_load((_TCK / "index.yaml").read_text(encoding="utf-8"))
        manifest["extensions"] = extensions
        issues = TestValidator().validate_tck(TckDefinition.model_validate(manifest), _TCK).issues
        return [i for i in issues if i.level == "error" and "experimental_extensions" in i.message]

    def test_the_shipped_manifest_enables_both(self) -> None:
        assert self._errors(["cac", "labs"]) == []

    def test_without_cac_the_references_are_refused(self) -> None:
        assert {e.field for e in self._errors(["labs"])} == {"cac", "validate.cac"}

    def test_without_labs_the_retry_parameters_and_labs_steps_are_refused(self) -> None:
        fields = {e.field for e in self._errors(["cac"])}
        assert fields == {"uses", "with.retry_on", "with.retry_attempts", "with.retry_delay_s"}

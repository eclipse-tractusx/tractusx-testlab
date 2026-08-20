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


"""The e2e scenarios, executed here — the steps, not just the YAML.

`testlab validate` proves an e2e test is well-formed and `testlab compile`
proves it packages. Neither runs a step, so a scenario can be valid, compile
cleanly, and then fail on its first call in a job that costs 25 minutes and a
Kubernetes cluster to reach. Everything in `tests/e2e/` that this repo can
drive without a dataspace is driven here instead, against the connector and
HTTP doubles, so the wiring, the `returns:` names and the assertions are known
good before the cluster is ever built.

What this cannot say anything about is the dataspace itself — whether two real
EDCs complete a DSP handshake, whether the IdentityHub issues a usable token,
whether the registry is reachable at the ingress path. That is what
`e2e-umbrella.yml` is for. The division is: shape and wiring here, dataspace
there.

The step lists are read out of the shipped YAML rather than restated, so a
scenario edited in `tests/e2e/` is the scenario this runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from combinations.connector_double import ConsumerDouble, ProviderDouble, ServicesDouble
from combinations.harness import Harness, build_context
from combinations.http_double import HttpDouble, Response

pytestmark = pytest.mark.asyncio

_SCENARIOS = Path("tests/e2e/connector-dtr-smoke/tests")

#: The asset the step-by-step scenario provisions and then negotiates for.
_ASSET_ID = "testlab-e2e-stepwise-asset"
_DCT_TYPE = "https://w3id.org/catenax/taxonomy#TestData"


def _phase(scenario: str, phase: str) -> list[dict]:
    """The steps of one phase, as the shipped file declares them."""
    document = yaml.safe_load((_SCENARIOS / scenario).read_text(encoding="utf-8"))
    return document.get(phase) or []


def _offered_catalog() -> dict:
    """A catalog answering with the one offer the scenario filtered for."""
    return {
        "dcat:dataset": [
            {
                "@id": "offer-1",
                "edc:id": _ASSET_ID,
                "dct:type": {"@id": _DCT_TYPE},
                "odrl:hasPolicy": {"@id": "offer-1"},
            }
        ]
    }


def _harness(consumer: ConsumerDouble, **seed: Any) -> Harness:
    harness = Harness(build_context(services=ServicesDouble(consumer, ProviderDouble())))
    harness.seed(
        **{
            "infrastructure.sut.connector.dsp_url": "http://provider.local/api/v1/dsp",
            "infrastructure.sut.connector.participant_id": "BPNL000000000001",
            **seed,
        }
    )
    return harness


class TestDspStepByStep:
    """The six-step journey, run step by step.

    The claim is that each step reads what the one before it published, so
    every assertion here is about a value having *travelled* — the asset id the
    negotiation asked for came out of the catalog, the URL the fetch called
    came out of the EDR.
    """

    @pytest.fixture
    def dataplane(self) -> HttpDouble:
        http = HttpDouble()
        http.json_route("GET", "/", {"payload": "the asset's data"})
        yield http
        http.stop()

    @pytest.fixture
    def consumer(self, dataplane: HttpDouble) -> ConsumerDouble:
        return ConsumerDouble(_offered_catalog(), dataplane.start())

    @pytest.fixture
    async def journey(self, consumer: ConsumerDouble):
        harness = _harness(
            consumer,
            **{
                "usage_policy": {"permission": []},
                "setup.asset.asset_id": _ASSET_ID,
            },
        )
        return await harness.run(*_phase("dsp_step_by_step.yaml", "execution"))

    async def test_the_file_declares_the_six_steps_the_scenario_is_named_for(self) -> None:
        steps = _phase("dsp_step_by_step.yaml", "execution")
        assert [step["id"] for step in steps] == [
            "catalog",
            "dataset",
            "negotiation",
            "transfer",
            "edr",
            "fetch",
        ]

    async def test_every_step_passes(self, journey) -> None:
        assert journey.passed, [(r.step_name, r.error) for r in journey.failures]

    async def test_the_negotiation_targets_the_asset_the_catalog_offered(
        self, journey, consumer: ConsumerDouble
    ) -> None:
        """Two hops: the catalog's offer through `extract_dataset` into
        `negotiate`. A reference that stopped resolving would arrive as None."""
        assert consumer.args_of("start_edr_negotiation")["target"] == _ASSET_ID

    async def test_the_negotiation_addresses_the_sut_from_the_infrastructure_binding(
        self, journey, consumer: ConsumerDouble
    ) -> None:
        asked = consumer.args_of("start_edr_negotiation")
        assert asked["counter_party_address"] == "http://provider.local/api/v1/dsp"
        assert asked["counter_party_id"] == "BPNL000000000001"

    async def test_the_fetch_spends_the_edr_the_transfer_produced(
        self, journey, dataplane: HttpDouble
    ) -> None:
        """The step that proves the chain carried real values.

        A data-plane URL assembled from an unresolved reference is not a URL,
        and does not arrive at a server.
        """
        assert [request.path for request in dataplane.received] == ["/"]

    async def test_every_declared_check_was_evaluated(self, journey) -> None:
        declared = sum(
            len(step.get("validate") or []) for step in _phase("dsp_step_by_step.yaml", "execution")
        )
        assert sum(len(r.assertions) for r in journey.results) == declared

    async def test_a_break_is_attributed_to_the_step_that_caused_it(
        self, consumer: ConsumerDouble
    ) -> None:
        """Why the journey is worth writing as six steps instead of one.

        With nothing in the catalog, the *catalog* step is the one that fails,
        on its own assertion, naming the empty offer list. Run as a single
        ``pull_data_filtered`` the same dataspace state surfaces at the end of
        the flow, and the operator has the whole journey to bisect.

        The harness runs every step regardless — that is what makes the
        attribution visible here. Under the player the phase stops at this
        first failure (``FailurePolicy.STOP``), so nothing downstream runs at
        all.
        """
        consumer._catalog = {"dcat:dataset": []}
        harness = _harness(
            consumer,
            **{"usage_policy": {"permission": []}, "setup.asset.asset_id": _ASSET_ID},
        )
        outcome = await harness.run(*_phase("dsp_step_by_step.yaml", "execution"))

        catalog = outcome.result("catalog")
        assert catalog.status.value == "FAILED"
        assert [a.passed for a in catalog.assertions] == [False, False]
        assert outcome.results[0] is catalog, "the first step is the one that broke"


class TestNegativePaths:
    """Absence, reported as absence."""

    @pytest.fixture
    def registry(self) -> HttpDouble:
        http = HttpDouble()
        http.route(
            "GET",
            "/api/v3.0/shell-descriptors/dXJuOnV1aWQ6dGVzdGxhYi1lMmUtYWJzZW50",
            Response(status=404, body={"messages": ["shell descriptor not found"]}),
        )
        http.route(
            "GET",
            "/api/v3.0/shell-descriptors",
            Response(status=401, body={"error": "unauthorized"}),
        )
        yield http
        http.stop()

    @pytest.fixture
    async def outcome(self, registry: HttpDouble):
        base = registry.start()
        # An EDC answering a filter that matched nothing sends a catalog
        # document with no offers in it, not an empty response.
        consumer = ConsumerDouble({"@context": {}, "@type": "dcat:Catalog"}, base)
        harness = _harness(consumer, **{"infrastructure.sut.dtr.base_url": base})
        return await harness.run(*_phase("negative_paths.yaml", "execution"))

    async def test_every_step_passes(self, outcome) -> None:
        """Every step here asks for something absent, and asserts the refusal."""
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    async def test_a_catalog_that_matched_nothing_reports_no_offers(self, outcome) -> None:
        assert outcome.result("catalog_for_nothing").status.value == "PASSED"

    async def test_the_registrys_404_is_read_off_the_wire(self, outcome) -> None:
        """Not fabricated. The step reports the status the registry sent."""
        result = outcome.result("twin_that_is_not_there")
        assert result.response is not None
        assert result.response.status_code == 404

    async def test_the_unauthenticated_call_reports_the_refusal_it_got(self, outcome) -> None:
        result = outcome.result("unauthenticated_dataplane")
        assert result.response is not None
        assert result.response.status_code == 401


class TestTheScenariosAreShipped:
    """The manifest and the files agree, so neither can be edited alone."""

    async def test_every_declared_test_file_exists(self) -> None:
        manifest = yaml.safe_load(
            Path("tests/e2e/connector-dtr-smoke/index.yaml").read_text(encoding="utf-8")
        )
        for entry in manifest["tests"]:
            assert (_SCENARIOS / entry["id"]).exists(), entry["id"]

    async def test_every_scenario_file_is_declared(self) -> None:
        manifest = yaml.safe_load(
            Path("tests/e2e/connector-dtr-smoke/index.yaml").read_text(encoding="utf-8")
        )
        declared = {entry["id"] for entry in manifest["tests"]}
        assert {path.name for path in _SCENARIOS.glob("*.yaml")} == declared

    async def test_the_scenarios_this_file_drives_are_still_the_shipped_ones(self) -> None:
        """A scenario renamed without updating this file would silently stop
        being covered, because `_phase` would read an empty document."""
        for scenario in ("dsp_step_by_step.yaml", "negative_paths.yaml"):
            assert _phase(scenario, "execution"), scenario

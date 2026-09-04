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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.


"""The two e2e scenarios `test_e2e_scenarios_offline.py` could not yet drive.

`connector_negotiation.yaml` and `dtr_roundtrip.yaml` were the only scripts in
`tests/e2e/` with no coverage outside the cluster, and both paid for it: a
`validate:` block that names something the step does not return is accepted by
`testlab validate`, compiles, and then fails on every run of a job that costs a
Kubernetes cluster to reach. That is what happened to the negotiation's
data-plane fetch, which asserted on an input named after the step instead of on
the status and body the step publishes.

The registry scenario runs against a real `AasService` pointed at a loopback
server, so the URLs, the base64 identifier encoding and the descriptor
serialisation are the SDK's own — only the registry behind them is local.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from combinations.connector_double import ConsumerDouble, ProviderDouble, ServicesDouble
from combinations.harness import Harness, build_context
from combinations.http_double import HttpDouble, Response
from tractusx_testlab.models import ServiceNotFoundError

pytestmark = pytest.mark.asyncio

_SCENARIOS = Path("tests/e2e/connector-dtr-smoke/tests")

#: The asset `connector_negotiation.yaml` provisions and then negotiates for.
_ASSET_ID = "testlab-e2e-smoke-asset"
_DCT_TYPE = "https://w3id.org/catenax/taxonomy#TestData"

#: Where the registry answers, as the workflow discovers it.
_REGISTRY_API_PATH = "/api/v3"


def _phase(scenario: str, phase: str) -> list[dict]:
    """The steps of one phase, as the shipped file declares them."""
    document = yaml.safe_load((_SCENARIOS / scenario).read_text(encoding="utf-8"))
    return document.get(phase) or []


class TestConnectorNegotiation:
    """The one-step DSP journey, and the fetch that spends what it produced."""

    @pytest.fixture
    def dataplane(self) -> HttpDouble:
        http = HttpDouble()
        http.json_route("GET", "/", {"payload": "the asset's data"})
        yield http
        http.stop()

    @pytest.fixture
    def consumer(self, dataplane: HttpDouble) -> ConsumerDouble:
        catalog = {
            "dcat:dataset": [
                {
                    "@id": _ASSET_ID,
                    "dct:type": {"@id": _DCT_TYPE},
                    "odrl:hasPolicy": {"@id": "offer-1"},
                }
            ]
        }
        return ConsumerDouble(catalog, dataplane.start())

    @pytest.fixture
    async def journey(self, consumer: ConsumerDouble):
        harness = Harness(build_context(services=ServicesDouble(consumer, ProviderDouble())))
        harness.seed(
            **{
                "infrastructure.sut.connector.dsp_url": "http://provider.local/api/v1/dsp/2025-1",
                "infrastructure.sut.connector.participant_id": "BPNL000000000001",
                "usage_policy": {"permissions": []},
                "setup.create_asset.asset_id": _ASSET_ID,
            }
        )
        return await harness.run(*_phase("connector_negotiation.yaml", "execution"))

    async def test_every_step_passes(self, journey) -> None:
        assert journey.passed, [(r.step_name, r.error) for r in journey.failures]

    async def test_every_assertion_names_something_the_step_returned(self, journey) -> None:
        """The defect this file was written for.

        An `input:` that names no output of its step resolves to `None`, and
        the assertion then fails whatever the dataspace answered — silently,
        because nothing before the run rejects the name.
        """
        failed = [
            (result.step_name, assertion.message)
            for result in journey.results
            for assertion in result.assertions
            if not assertion.passed
        ]
        assert failed == []

    async def test_the_fetch_spends_the_edr_the_flow_produced(
        self, journey, dataplane: HttpDouble
    ) -> None:
        assert [request.path for request in dataplane.received] == ["/"]

    async def test_the_flow_addresses_the_sut_from_the_infrastructure_binding(
        self, journey, consumer: ConsumerDouble
    ) -> None:
        asked = consumer.args_of("get_transfer_id")
        assert asked["counter_party_address"] == "http://provider.local/api/v1/dsp/2025-1"
        assert asked["counter_party_id"] == "BPNL000000000001"


class _RegistryServices:
    """A `ServiceManager` stand-in holding one registry.

    `DataspaceAccess` walks `service_names` and asks `get` for a type, so that
    pair plus `definition_of_type` is the whole surface a registry double needs.
    """

    def __init__(self, registry: Any) -> None:
        self._registry = registry

    @property
    def service_names(self) -> list[str]:
        return ["DTR"]

    def definition_of_type(self, service_type: Any) -> object | None:
        return None

    def get(self, name: str, service_type: Any) -> Any:
        wanted = getattr(service_type, "name", str(service_type))
        if wanted != "DTR":
            raise ServiceNotFoundError(name)
        return self._registry


class _RegistryDouble:
    """A registry that keeps whatever descriptor was written to it.

    Enough of the Tractus-X DTR for a round-trip: a POST stores the document
    and echoes it back as the registry does, a GET returns what is stored, and
    a DELETE answers 204. Anything else is a 404, so a step that builds the
    wrong URL fails here rather than passing on a fixture that answers
    everything.
    """

    def __init__(self) -> None:
        self.http = HttpDouble()
        self.stored: dict = {}
        self.http._next_response = self._answer

    def start(self) -> str:
        return self.http.start()

    def stop(self) -> None:
        self.http.stop()

    @property
    def received(self) -> list:
        return self.http.received

    def _answer(self, method: str, path: str) -> Response:
        descriptors = f"{_REGISTRY_API_PATH}/shell-descriptors"
        if method == "POST" and path == descriptors:
            self.stored = self.http.received[-1].body or {}
            return Response(status=201, body=self.stored)
        if method == "GET" and path.startswith(f"{descriptors}/"):
            return Response(status=200, body=self.stored)
        if method == "DELETE" and path.startswith(f"{descriptors}/"):
            return Response(status=204, body=None)
        return Response(status=404, body={"messages": [f"no route for {method} {path}"]})


class TestDtrRoundTrip:
    """Write a shell descriptor, read it back, delete it."""

    @pytest.fixture
    def registry(self) -> _RegistryDouble:
        double = _RegistryDouble()
        yield double
        double.stop()

    @pytest.fixture
    def harness(self, registry: _RegistryDouble) -> Harness:
        from tractusx_sdk.industry.services.aas_service import AasService

        base = registry.start()
        service = AasService(base_url=base, base_lookup_url=base, api_path=_REGISTRY_API_PATH)
        harness = Harness(build_context(services=_RegistryServices(service)))
        harness.seed(
            **{
                "infrastructure.sut.connector.dsp_url": "http://provider.local/api/v1/dsp/2025-1",
                "infrastructure.sut.connector.participant_id": "BPNL000000000001",
            }
        )
        return harness

    @pytest.fixture
    async def written(self, harness: Harness):
        return await harness.run(*_phase("dtr_roundtrip.yaml", "execution"))

    async def test_every_step_passes(self, written) -> None:
        assert written.passed, [(r.step_name, r.error) for r in written.failures]

    async def test_the_descriptor_reaches_the_registrys_own_api_path(
        self, written, registry: _RegistryDouble
    ) -> None:
        """A path the registry does not serve answers 404, not a descriptor."""
        assert registry.received[0].path == f"{_REGISTRY_API_PATH}/shell-descriptors"

    async def test_the_submodel_endpoint_carries_what_the_registry_demands(
        self, written, registry: _RegistryDouble
    ) -> None:
        """The two fields the Tractus-X registry rejects a descriptor without.

        Both are optional in the AAS specification and neither is optional
        here, so a scenario that drops one compiles and then fails against the
        live registry alone.
        """
        endpoint = registry.stored["submodelDescriptors"][0]["endpoints"][0]
        protocol = endpoint["protocolInformation"]
        assert protocol["endpointProtocolVersion"] == ["1.1"]
        assert protocol["securityAttributes"] == [{"type": "NONE", "key": "NONE", "value": "NONE"}]

    async def test_the_teardown_deletes_the_twin_this_run_created(
        self, harness: Harness, written, registry: _RegistryDouble
    ) -> None:
        outcome = await harness.run(*_phase("dtr_roundtrip.yaml", "teardown"), phase="teardown")

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert registry.received[-1].method == "DELETE"

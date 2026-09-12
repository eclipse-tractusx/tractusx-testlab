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


"""The seven scenarios added after `test_e2e_scenarios_offline.py`, run here.

The division that file draws holds for these too: shape and wiring here,
dataspace in `e2e-umbrella.yml`. What is new is how much of the seven can be
reached without one. `engine_toolbox.yaml` addresses no connector and no
registry at all, so it runs here whole, against the real mock server;
`catalog_variants.yaml` runs against the connector doubles; the descriptor
chain in the middle of `industry_core_journey.yaml` runs on a seeded document,
because that chain is pure parsing and a wrong JSON path there yields `None`
rather than an error.

The other three — `notification_roundtrip.yaml`, `dtr_consumer_dataplane.yaml`
and `push_transfer.yaml` — need two live connectors before a single step of
theirs does anything, so what is asserted about them is what is settled in the
file: the fields whose value decides whether a run fails in the cluster
twenty-five minutes in, or does not fail at all when it should have. Each
class says which.

Step lists and `with:` blocks are read out of the shipped YAML, so a scenario
edited in `tests/e2e/` is the scenario this reasons about.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import yaml

from combinations.connector_double import ConsumerDouble, ProviderDouble, ServicesDouble
from combinations.harness import Harness, build_context
from combinations.http_double import HttpDouble
from combinations.mock_server_double import MockServer
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks

pytestmark = pytest.mark.asyncio

_SCENARIOS = Path("tests/e2e/connector-dtr-smoke/tests")
_MANIFEST = Path("tests/e2e/connector-dtr-smoke/index.yaml")

#: The scenarios this file is about. The two already covered by
#: `test_e2e_scenarios_offline.py` and the two covered by the inbound and
#: callback files are deliberately not here.
_NEW_SCENARIOS = (
    "catalog_variants.yaml",
    "bpn_discovery.yaml",
    "push_transfer.yaml",
    "dtr_consumer_dataplane.yaml",
    "notification_roundtrip.yaml",
    "industry_core_journey.yaml",
    "engine_toolbox.yaml",
)

#: `${{ env.<id> }}`, but not the two namespaces that are not variables:
#: `env.schemas.*` and `env.testdata.*` are declared in their own manifest
#: blocks and resolve through them.
_ENV_REFERENCE = re.compile(r"\$\{\{\s*env\.([a-z_][a-z0-9_]*)")

#: `${{ infrastructure.<side>.<capability>.<field> }}`.
_INFRASTRUCTURE_REFERENCE = re.compile(
    r"\$\{\{\s*infrastructure\.([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_-]*)\."
)

#: The catalog offers `catalog_variants.yaml` provisions, in the order the
#: provider would answer with them.
_CATALOG_ASSET = "testlab-e2e-catalog-asset"
_WIZARD_ASSET = "testlab-e2e-wizard-asset"


def _document(scenario: str) -> dict:
    """The shipped scenario, as YAML."""
    return yaml.safe_load((_SCENARIOS / scenario).read_text(encoding="utf-8"))


def _phase(scenario: str, phase: str) -> list[dict]:
    """The steps of one phase, as the shipped file declares them."""
    return _document(scenario).get(phase) or []


def _step(scenario: str, phase: str, step_id: str) -> dict:
    """One step of a phase, by the id the file gives it."""
    for step in _phase(scenario, phase):
        if step.get("id") == step_id:
            return step
    raise AssertionError(
        f"{scenario} declares no {phase} step {step_id!r}. "
        f"It declares: {[s.get('id') for s in _phase(scenario, phase)]}"
    )


def _manifest() -> dict:
    return yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))


def _manifest_variable(variable_id: str) -> Any:
    """The value a `env.variables` entry publishes, as a test reads it."""
    for entry in _manifest()["env"]["variables"]:
        if entry["id"] == variable_id:
            return entry["with"]["value"]
    raise AssertionError(f"The manifest declares no env variable {variable_id!r}")


class TestTheManifestObligesWhatTheScenariosNeed:
    """Two ways a test depends on something no operator was asked for.

    `testlab validate` reads each file on its own, so a reference to an
    undeclared variable and a reference to an optional capability both compile.
    The first fails the run at its first step with an unresolved reference; the
    second fails it in whichever deployment left that capability out — which is
    every deployment except the one the author happened to write it in.
    """

    @pytest.mark.parametrize("scenario", _NEW_SCENARIOS)
    async def test_every_env_variable_it_reads_is_one_the_manifest_declares(
        self, scenario: str
    ) -> None:
        text = (_SCENARIOS / scenario).read_text(encoding="utf-8")
        declared = {entry["id"] for entry in _manifest()["env"]["variables"]}
        read = {
            name
            for name in _ENV_REFERENCE.findall(text)
            # `env.schemas` and `env.testdata` are namespaces, not variables.
            if name not in {"schemas", "testdata"}
        }
        assert read <= declared, sorted(read - declared)

    @pytest.mark.parametrize("scenario", _NEW_SCENARIOS)
    async def test_every_binding_it_reads_is_one_the_manifest_requires(self, scenario: str) -> None:
        """A capability declared `required: false` may not be bound at all, and
        a reference to an unbound binding resolves to nothing."""
        text = (_SCENARIOS / scenario).read_text(encoding="utf-8")
        infrastructure = _manifest()["infrastructure"]
        for side, capability in set(_INFRASTRUCTURE_REFERENCE.findall(text)):
            declared = infrastructure.get(side, {}).get(capability)
            assert declared is not None, f"{side}.{capability} is not declared"
            assert declared.get("required") is True, f"{side}.{capability} is not required"


class TestEngineToolbox:
    """The one scenario of the seven that runs whole with no dataspace at all.

    It addresses no connector and no registry: its endpoints are the mock
    server's own, so everything it drives — the OAuth2 clients, the two
    protocol mocks, the utility chain, the branch and the retry — is driven
    here exactly as the cluster would drive it. There is nothing left for
    `e2e-umbrella.yml` to add, which makes this the file's highest-value test:
    a regression in the engine's own toolbox fails in seconds instead of in a
    twenty-five minute job.
    """

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
    async def outcome(self, server: MockServer):
        harness = Harness(build_context(config=server.config))
        opened = await harness.run(*_phase("engine_toolbox.yaml", "setup"), phase="setup")
        assert opened.passed, [(r.step_name, r.error) for r in opened.failures]
        return await harness.run(*_phase("engine_toolbox.yaml", "execution"))

    async def test_every_step_passes(self, outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    async def test_every_declared_check_was_evaluated(self, outcome) -> None:
        declared = sum(
            len(step.get("validate") or []) for step in _phase("engine_toolbox.yaml", "execution")
        )
        assert sum(len(r.assertions) for r in outcome.results) == declared

    async def test_all_three_grants_came_back_with_the_token_the_endpoint_issued(
        self, outcome
    ) -> None:
        """Read off the run rather than off the file: the scenario's own
        `validate:` blocks say the same thing, and would say it just as loudly
        if the engine had stopped evaluating them."""
        for step_id in ("oauth_client_credentials", "oauth_password", "oauth_refresh"):
            published = outcome.variables[f"execution.{step_id}.access_token"]
            assert published == "testlab-e2e-access-token", step_id

    async def test_the_refresh_grant_spent_the_token_the_first_grant_earned(self, outcome) -> None:
        """The third step's input is the first step's output, so this is the
        one place in the scenario where a token *travelled*."""
        earned = outcome.variables["execution.oauth_client_credentials.refresh_token"]
        assert earned == "testlab-e2e-refresh-token"
        assert outcome.result("oauth_refresh").request is not None

    async def test_the_registry_mock_filtered_rather_than_answering_with_both_shells(
        self, outcome
    ) -> None:
        """The mock holds two shells and the criteria name one. A registry mock
        that ignored its criteria would answer every lookup in the suite
        correctly by accident, and no assertion written against a one-twin
        registry could tell."""
        first_shell = _step("engine_toolbox.yaml", "setup", "registry_mock")["with"]["shells"][0]
        for step_id in ("lookup_by_asset_ids", "lookup_by_asset_link"):
            found = outcome.variables[f"execution.{step_id}.shell_ids"]
            assert found == [first_shell["id"]], step_id

    async def test_a_field_check_reaches_into_a_top_level_json_array(self) -> None:
        """`discovery_probe` depends on this, and it did not always hold.

        The discovery finder answers with a bare JSON array — the shape the
        step's own comment says a test depends on — and `extract_path` used
        to traverse only dicts from the root, handing anything else to
        `getattr`. Every spelling of an index resolved to `None`, so a
        `validate/field` check failed against a correct answer and said
        nothing about why. A list root is now walked like a dict root, which
        is what the scenario's two checks on that step rely on, and this is
        the assertion that keeps it that way.
        """
        from tractusx_testlab.steps._checks.extraction import extract_path

        answered = [{"bpn": "BPNL000000000001", "connectorEndpoint": ["http://dsp.local"]}]
        assert extract_path(answered, "0.bpn") == "BPNL000000000001"
        assert extract_path(answered, "0.connectorEndpoint.0") == "http://dsp.local"
        # A predicate still needs a key to select through — `result[bpn='…']`,
        # not a bare `[bpn='…']` — so a list root is indexable and filterable
        # one level in, which is what the AAS and discovery answers need.
        assert extract_path({"result": answered}, "result[bpn='BPNL000000000001'].bpn") == (
            "BPNL000000000001"
        )


class TestCatalogVariants:
    """The four consumer-side catalog paths, run against the doubles.

    Each of the four reaches the SDK by a different call, and the scenario
    tells them apart only by what it asserts on the answer. What the doubles
    add is the other half: what each step *asked for*. A catalog query that
    filtered by the wrong id and a pull that accepted an offer under the wrong
    policy both come back with a plausible answer from a real connector, and
    the scenario's own checks would pass on it.
    """

    @pytest.fixture()
    def dataplane(self) -> Generator[HttpDouble, None, None]:
        http = HttpDouble()
        http.json_route("GET", "/", {"payload": "the asset's data"})
        yield http
        http.stop()

    @pytest.fixture()
    def consumer(self, dataplane: HttpDouble) -> ConsumerDouble:
        """A provider offering both assets setup registers, document form first."""
        catalog = {
            "dcat:dataset": [
                {
                    "@id": asset_id,
                    "edc:id": asset_id,
                    "dct:type": {"@id": "https://w3id.org/catenax/taxonomy#TestData"},
                    "odrl:hasPolicy": [{"@id": f"offer-{asset_id}", "odrl:permission": []}],
                }
                for asset_id in (_CATALOG_ASSET, _WIZARD_ASSET)
            ]
        }
        return ConsumerDouble(catalog, dataplane.start())

    @pytest.fixture()
    async def outcome(self, consumer: ConsumerDouble):
        harness = Harness(build_context(services=ServicesDouble(consumer, ProviderDouble())))
        harness.seed(
            **{
                "infrastructure.sut.connector.dsp_url": "http://provider.local/api/v1/dsp",
                "infrastructure.sut.connector.participant_id": "BPNL000000000001",
                # The policy the manifest publishes, not a stand-in: what the
                # pull hands the SDK is asserted against it below.
                "usage_policy": _manifest_variable("usage_policy"),
                "setup.create_asset.asset_id": _CATALOG_ASSET,
                "setup.create_wizard_asset.asset_id": _WIZARD_ASSET,
            }
        )
        return await harness.run(*_phase("catalog_variants.yaml", "execution"))

    async def test_every_step_passes(self, outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    async def test_every_declared_check_was_evaluated(self, outcome) -> None:
        declared = sum(
            len(step.get("validate") or []) for step in _phase("catalog_variants.yaml", "execution")
        )
        assert sum(len(r.assertions) for r in outcome.results) == declared

    async def test_the_filtered_query_asked_for_the_asset_setup_registered(
        self, outcome, consumer: ConsumerDouble
    ) -> None:
        """The id is wired from `setup.create_asset.asset_id`, and the step's
        own check compares the answer against a literal — so a reference that
        stopped resolving would ask for `None` and still be judged against
        `testlab-e2e-catalog-asset`."""
        assert consumer.args_of("get_catalog_by_asset_id")["asset_id"] == _CATALOG_ASSET

    async def test_the_strict_pull_was_given_the_manifests_usage_policy(
        self, outcome, consumer: ConsumerDouble
    ) -> None:
        """`pull_data_filtered_by_policy` accepts an offer only under a policy
        it was named, so the policy reaching the SDK is what decides whether
        the run negotiates at all. It arrives translated out of the manifest's
        simplified spelling, and translated to nothing would be indistinguish-
        able from translated correctly, on the doubles and on a connector."""
        declared = _manifest_variable("usage_policy")["permissions"][0]["constraints"][0]["and"]
        given = consumer.args_of("get_transfer_id")["policies"]

        assert given is not None and len(given) == 1
        # The authoring key the manifest carries for testlab's own sake; a
        # catalog offer has no such key and cannot match one.
        assert "policy_id" not in given[0]
        permission = given[0]["permission"][0]
        assert permission["action"] == "use"
        assert [c["rightOperand"] for c in permission["constraint"][0]["and"]] == [
            constraint["right_operand"] for constraint in declared
        ]

    async def test_the_strict_pull_filtered_for_the_wizard_asset_not_the_other_one(
        self, outcome, consumer: ConsumerDouble
    ) -> None:
        """Two offers stand in the catalog and the pull reports the first one
        it was answered with, so the filter is the only thing that makes
        `asset_id` the wizard asset rather than whichever offer came first."""
        asked = [
            entry["operandRight"]
            for _name, kwargs in consumer.calls
            if _name == "get_transfer_id"
            for entry in kwargs["filter_expression"]
        ]
        assert asked == [_WIZARD_ASSET]
        assert outcome.variables["execution.pull_wizard_asset.asset_id"] == _WIZARD_ASSET

    async def test_both_fetches_spent_the_edr_the_flow_before_them_produced(
        self, outcome, dataplane: HttpDouble
    ) -> None:
        """A data-plane URL assembled from an unresolved reference is not a URL
        and does not arrive at a server; two calls arrived."""
        assert [request.path for request in dataplane.received] == ["/", "/"]


class TestIndustryCoreJourney:
    """The chain that decodes the descriptor, on a descriptor the registry gave.

    The journey as a whole needs a registry and a submodel server, so it is not
    run. What is run is the part of it a consumer performs on a document alone:
    the subprotocol body out of the shell descriptor, and the asset id and DSP
    endpoint out of that. It is the part most likely to break silently — a
    wrong JSON path yields `None` and a wrong key separator yields a truncated
    URL, and either negotiates for the wrong thing instead of failing.

    The endpoint in the descriptor carries a query string on purpose: that is
    the case where a parser splitting every pair on every `=` still hands back
    something that looks like an address.
    """

    _DSP_URL = "http://provider-dsp.local/api/v1/dsp/2025-1?protocol=dsp&version=2025-1"
    _ASSET_ID = "testlab-e2e-ic-asset"

    @pytest.fixture()
    def descriptor(self) -> dict:
        """A shell descriptor as the Tractus-X registry answers with one."""
        return {
            "id": "urn:uuid:9f1a4c20-0000-4000-8000-000000000002",
            "idShort": "testlabE2eSerialPart",
            "globalAssetId": "urn:uuid:9f1a4c20-0000-4000-8000-000000000001",
            "submodelDescriptors": [
                {
                    "id": "urn:uuid:9f1a4c20-0000-4000-8000-000000000003",
                    "idShort": "serialPartSubmodel",
                    "semanticId": {
                        "type": "ExternalReference",
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": "urn:samm:io.catenax.serial_part:3.0.0#SerialPart",
                            }
                        ],
                    },
                    "endpoints": [
                        {
                            "interface": "SUBMODEL-3.0",
                            "protocolInformation": {
                                "href": "http://submodels.local/urn:uuid:9f1a4c20",
                                "endpointProtocol": "HTTP",
                                "endpointProtocolVersion": ["1.1"],
                                "subprotocol": "DSP",
                                "subprotocolBody": (
                                    f"id={self._ASSET_ID};dspEndpoint={self._DSP_URL}"
                                ),
                                "subprotocolBodyEncoding": "plain",
                            },
                        }
                    ],
                }
            ],
        }

    @pytest.fixture()
    async def outcome(self, descriptor: dict):
        harness = Harness(build_context())
        harness.seed(
            **{
                "infrastructure.sut.connector.dsp_url": self._DSP_URL,
                "execution.read_twin.body": descriptor,
            }
        )
        return await harness.run(
            *[
                _step("industry_core_journey.yaml", "execution", step_id)
                for step_id in (
                    "subprotocol_body",
                    "negotiated_asset_id",
                    "negotiated_dsp_endpoint",
                )
            ]
        )

    async def test_every_step_of_the_chain_passes(self, outcome) -> None:
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]

    async def test_the_subprotocol_body_was_found_where_the_descriptor_keeps_it(
        self, outcome, descriptor: dict
    ) -> None:
        """Three predicate hops down a document nobody indexed. A path that
        missed by one segment returns `None`, not an error."""
        stored = descriptor["submodelDescriptors"][0]["endpoints"][0]["protocolInformation"]
        assert outcome.variables["execution.subprotocol_body.value"] == stored["subprotocolBody"]

    async def test_the_asset_id_parsed_out_is_the_one_the_descriptor_named(self, outcome) -> None:
        assert outcome.variables["execution.negotiated_asset_id.value"] == self._ASSET_ID

    async def test_the_endpoint_survived_its_own_query_string(self, outcome) -> None:
        """The value is a URL, and a URL carrying a query string carries `=`.
        Split on every `=` it comes back as `http://…/2025-1?protocol`, which is
        still an address and still negotiates — with nobody."""
        assert outcome.variables["execution.negotiated_dsp_endpoint.value"] == self._DSP_URL

    async def test_the_pull_is_addressed_at_the_parsed_endpoint_not_at_the_binding(
        self,
    ) -> None:
        """The regression this whole chain exists to catch. Read from
        `infrastructure.sut.connector.dsp_url` the pull reaches the right
        connector in this deployment, every assertion above still passes, and
        the descriptor decoding becomes decorative — a consumer that had never
        seen the provider would have nothing to go on.
        """
        pull = _step("industry_core_journey.yaml", "execution", "pull_submodel_asset")["with"]
        assert pull["counter_party_address"] == "${{ execution.negotiated_dsp_endpoint.value }}"
        assert pull["filters"][0]["operand_right"] == "${{ execution.negotiated_asset_id.value }}"


class TestNotificationRoundtrip:
    """What is settled in the file, for a scenario that needs two connectors.

    Nothing here runs: `notification/consumer/send` discovers, negotiates and
    transfers before it posts anything. The three things asserted are the ones
    whose failure mode is invisible until the cluster is up — a notification
    the SDK refuses outright, a second send that quietly repeats the first
    one's code path, and a wait on a mock nobody opened, which is a scenario
    that hangs for its whole timeout and then fails on the wait.
    """

    _SCENARIO = "notification_roundtrip.yaml"

    def _sends(self) -> list[dict]:
        return [
            step
            for step in _phase(self._SCENARIO, "execution")
            if step["uses"] == "notification/consumer/send"
        ]

    async def test_the_scenario_sends_twice(self) -> None:
        assert [step["id"] for step in self._sends()] == ["send_via_dsp", "send_direct"]

    async def test_sender_and_receiver_are_read_from_different_env_variables(self) -> None:
        """The SDK refuses a notification addressed to its own sender, and a
        deployment that bound both BPNs to one participant would fail every run
        of this scenario in the cluster and nowhere earlier."""
        for send in self._sends():
            header = send["with"]["notification"]["header"]
            assert header["senderBpn"] == "${{ env.engine_bpnl }}"
            assert header["receiverBpn"] == "${{ env.sut_bpnl }}"
            assert header["senderBpn"] != header["receiverBpn"]

    async def test_the_second_send_selects_direct_mode_by_carrying_an_edr(self) -> None:
        """Which of the step's two modes runs is decided by the presence of
        `dataplane_url`, not by a flag — so a second send that also named a
        counterparty would negotiate again and cover the first mode twice."""
        first, second = self._sends()
        assert "dataplane_url" not in first["with"]
        assert first["with"]["counter_party_address"]

        assert second["with"]["dataplane_url"] == (
            "${{ execution.pull_notification_api.dataplane_url }}"
        )
        assert second["with"]["edr_token"] == "${{ execution.pull_notification_api.edr_token }}"
        assert "counter_party_address" not in second["with"]

    async def test_both_waits_wait_on_a_mock_some_setup_step_opened(self) -> None:
        """A `mock/wait/http_request` given an unopened mock does not fail
        fast: it blocks for its declared timeout — sixty seconds here, each —
        and then reports that nothing arrived."""
        opened = {
            f"${{{{ setup.{step['id']}.mock }}}}"
            for step in _phase(self._SCENARIO, "setup")
            if step["uses"] == "mock/api"
        }
        waits = [
            step
            for step in _phase(self._SCENARIO, "execution")
            if step["uses"] == "mock/wait/http_request"
        ]
        assert len(waits) == 2
        for wait in waits:
            assert wait["with"]["mock"] in opened, wait["id"]

    async def test_each_wait_watches_the_endpoint_its_send_posted_to(self) -> None:
        """Two mocks and two sends: crossed over, both waits still resolve and
        the two modes are no longer told apart on the wire."""
        paths = {
            step["id"]: step["with"]["path"]
            for step in _phase(self._SCENARIO, "setup")
            if step["uses"] == "mock/api"
        }
        for send, wait_id in (
            (self._sends()[0], "await_notification"),
            (self._sends()[1], "await_direct_notification"),
        ):
            wait = _step(self._SCENARIO, "execution", wait_id)
            opener = wait["with"]["mock"].split(".")[1]
            assert send["with"]["endpoint_path"] == paths[opener], wait_id


class TestDtrConsumerDataplane:
    """What is settled in the file, for a scenario that needs a negotiated EDR.

    Every step of it spends a token a live negotiation produced, so none of it
    runs here. Two things about it are decidable from the file and expensive to
    get wrong: a registry step that read its address from a binding instead of
    from the EDR would pass in this deployment and prove nothing about the
    consumer path the scenario exists to exercise; and a twin whose visibility
    names only one spelling of the consumer's identity is readable or not
    depending on what the provider's data plane puts on the `Edc-Bpn` header,
    which is a deployment detail no test controls.
    """

    _SCENARIO = "dtr_consumer_dataplane.yaml"

    def _consumer_steps(self) -> list[dict]:
        return [
            step
            for step in _phase(self._SCENARIO, "execution")
            if step["uses"].startswith("digital-twin-registry/consumer/dataplane/")
            or step["uses"] == "connector/dataplane/http_request"
        ]

    async def test_the_scenario_reads_the_registry_through_the_data_plane_four_ways(
        self,
    ) -> None:
        assert [step["id"] for step in self._consumer_steps()] == [
            "list_shells",
            "lookup_by_part",
            "lookup_by_asset_link",
            "read_twin",
            "read_twin_raw",
        ]

    async def test_every_consumer_step_spends_the_edr_the_negotiation_produced(self) -> None:
        """Not the registry binding. `infrastructure.sut.dtr.base_url` reaches
        the same registry from the engine, so a step wired to it answers
        correctly here and never travels through a data plane at all — which is
        the entire subject of this scenario."""
        for step in self._consumer_steps():
            assert step["with"]["dataplane_url"] == (
                "${{ execution.registry_auth.dataplane_url }}"
            ), step["id"]
            assert step["with"]["edr_token"] == "${{ execution.registry_auth.edr_token }}", step[
                "id"
            ]

    async def test_the_twin_is_visible_under_both_spellings_of_the_consumer(self) -> None:
        """The connector's participant ID is a DID in Saturn and the BPN is
        what the data plane may put on the header instead. A twin naming one of
        the two is readable in one deployment and invisible in the next, and
        the failure is an empty lookup rather than an error."""
        specific = _step(self._SCENARIO, "setup", "create_shell")["with"]["specific_asset_ids"]
        named = {key["value"] for entry in specific for key in entry["externalSubjectId"]["keys"]}
        assert "${{ infrastructure.engine.connector.participant_id }}" in named
        assert "${{ env.engine_bpnl }}" in named

    async def test_the_criteria_the_lookups_search_by_carry_the_public_wildcard(self) -> None:
        """A criterion is answerable only if the twin grants the caller
        visibility of that identifier. Both lookups search by
        `manufacturerPartId`, and the body-carried one also by
        `digitalTwinType`, so both must carry the registry's wildcard or the
        search comes back empty for a partner that owns nothing here."""
        visibility = {
            entry["name"]: {key["value"] for key in entry["externalSubjectId"]["keys"]}
            for entry in _step(self._SCENARIO, "setup", "create_shell")["with"][
                "specific_asset_ids"
            ]
        }
        searched = {
            criterion["name"]
            for step in self._consumer_steps()
            for criterion in step["with"].get("specific_asset_ids") or []
        }
        assert searched, "no lookup searches by a specific asset id"
        for name in searched:
            assert "PUBLIC_READABLE" in visibility[name], name


class TestPushTransfer:
    """What is settled in the file, for the one transfer nobody can fetch.

    A push needs a provider that dials out, so the scenario does not run here.
    What the file decides on its own is the branch of
    `connector/consumer/initiate_transfer` it takes — a push runs under an
    agreement and produces no EDR, so naming a negotiation instead would send
    it down the pull branch and never push anything — and the address the
    provider is handed, which is dialled from a pod and not from the engine.
    """

    _SCENARIO = "push_transfer.yaml"

    @pytest.fixture()
    def push(self) -> dict:
        return _step(self._SCENARIO, "execution", "push")["with"]

    async def test_the_transfer_is_a_push(self, push: dict) -> None:
        assert push["transfer_type"].endswith("-PUSH")

    async def test_it_runs_under_the_agreement_the_negotiation_settled(self, push: dict) -> None:
        """The identifier a push takes is the agreement, not the negotiation:
        there is no EDR to collect, so the step has nothing to look one up by.
        A negotiation id here selects the pull branch instead."""
        assert push["agreement_id"] == "${{ execution.negotiation.agreement_id }}"
        assert "negotiation_id" not in push
        assert push["data_destination"]

    async def test_the_destination_is_an_address_a_pod_can_dial(self, push: dict) -> None:
        """`full_mock_url` is what a `mock/api` step reports, and it says
        `localhost` — true for the engine and useless to the provider's data
        plane, which is the party that dials this address."""
        sink = _step(self._SCENARIO, "setup", "open_push_sink")["with"]["path"]
        assert push["data_destination"]["baseUrl"] == ("${{ env.mock_server_external_url }}" + sink)
        assert "full_mock_url" not in str(push["data_destination"])

    async def test_the_delivery_is_read_off_the_mock_the_destination_names(self) -> None:
        """The transfer's own state says the provider believes it delivered.
        Only the mock says something arrived, and only if the wait watches the
        endpoint the destination named."""
        wait = _step(self._SCENARIO, "execution", "await_push")["with"]
        assert wait["mock"] == "${{ setup.open_push_sink.mock }}"

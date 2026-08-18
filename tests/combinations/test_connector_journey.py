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

"""The whole consumer journey, one step handing off to the next.

Catalog → dataset → negotiation → transfer → data plane is the flow nearly
every TCK is built out of, and each hop reads a name the hop before it
published. Tested one step at a time, all five pass while the chain is broken;
this runs them in sequence and then reads the data at the far end.

The last hop is a real HTTP request to a real socket, so the URL and token that
came out of the transfer have to be the ones that arrive at the data plane.
"""

from __future__ import annotations

import pytest

from combinations.connector_double import (
    ConsumerDouble,
    ProviderDouble,
    ServicesDouble,
)
from combinations.harness import Harness, build_context
from combinations.http_double import HttpDouble

pytestmark = pytest.mark.asyncio

_DCT_TYPE = "cx-taxo:DigitalTwinRegistry"
_ASSET_ID = "asset-dtr-1"

#: A catalog shaped the way the connector answers one.
CATALOG = {
    "dcat:dataset": [
        {
            "@id": "dataset-1",
            "edc:id": _ASSET_ID,
            "dct:type": {"@id": _DCT_TYPE},
            "odrl:hasPolicy": [{"@id": "offer-1", "odrl:permission": []}],
        },
        {
            "@id": "dataset-2",
            "edc:id": "asset-other",
            "dct:type": {"@id": "cx-taxo:SomethingElse"},
            "odrl:hasPolicy": [{"@id": "offer-2"}],
        },
    ]
}


def _journey(dataplane_path: str = "/api/public") -> list[dict]:
    """The five steps, wired only by ``${{ execution.<id>.<field> }}``."""
    return [
        {
            "id": "catalog",
            "uses": "connector/consumer/query_catalog",
            "with": {
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider/api/dsp",
            },
            "returns": {"datasets": {"type": "array"}},
        },
        {
            "id": "offer",
            "uses": "connector/consumer/extract_dataset",
            "with": {
                "datasets": "${{ execution.catalog.datasets }}",
                "dct_type": _DCT_TYPE,
            },
            "returns": {
                "asset_id": {"type": "string"},
                "offer_id": {"type": "string"},
                "dataset": {"type": "object"},
            },
        },
        {
            "id": "negotiate",
            "uses": "connector/consumer/negotiate",
            "with": {
                "counter_party_id": "BPNL000000000001",
                "counter_party_address": "https://provider/api/dsp",
                "asset_id": "${{ execution.offer.asset_id }}",
                "policy": "${{ execution.offer.dataset }}",
                "poll_interval": 0,
            },
            "returns": {
                "negotiation_id": {"type": "string"},
                "agreement_id": {"type": "string"},
                "state": {"type": "string"},
            },
        },
        {
            "id": "transfer",
            "uses": "connector/consumer/initiate_transfer",
            "with": {"negotiation_id": "${{ execution.negotiate.negotiation_id }}"},
            "returns": {
                "transfer_id": {"type": "string"},
                "dataplane_url": {"type": "string"},
                "edr_token": {"type": "string"},
            },
        },
        {
            "id": "pull",
            "uses": "connector/dataplane/http_request",
            "with": {
                "method": "GET",
                "dataplane_url": "${{ execution.transfer.dataplane_url }}",
                "edr_token": "${{ execution.transfer.edr_token }}",
                "path": dataplane_path,
            },
        },
    ]


@pytest.fixture()
def consumer(http: HttpDouble) -> ConsumerDouble:
    """A consumer whose EDR points at the live data-plane double."""
    http.json_route("GET", "/api/public", {"shells": ["urn:uuid:1"]})
    base = http.start()
    return ConsumerDouble(CATALOG, dataplane_url=base, token="Bearer edr-token")


@pytest.fixture()
def wired(consumer: ConsumerDouble) -> Harness:
    """A harness whose context resolves the consumer and provider services."""
    return Harness(
        build_context(services=ServicesDouble(consumer, ProviderDouble()))
    )


class TestTheConsumerJourney:
    """Five steps, each reading what the one before it declared."""

    async def test_every_step_of_the_journey_passes(
        self, wired: Harness, consumer: ConsumerDouble
    ) -> None:
        outcome = await wired.run(*_journey())
        assert outcome.passed, [
            (r.step_name, r.error) for r in outcome.failures
        ]

    async def test_the_data_arrives_at_the_far_end(
        self, wired: Harness, consumer: ConsumerDouble
    ) -> None:
        outcome = await wired.run(*_journey())
        assert outcome.output("pull") == {"shells": ["urn:uuid:1"]}

    async def test_the_catalog_selects_the_dataset_the_dct_type_names(
        self, wired: Harness
    ) -> None:
        outcome = await wired.run(*_journey())
        assert outcome.variables["asset_id"] == _ASSET_ID
        assert outcome.variables["offer_id"] == "offer-1"

    async def test_the_selected_asset_is_what_the_negotiation_asks_for(
        self, wired: Harness, consumer: ConsumerDouble
    ) -> None:
        """The hop most likely to go wrong silently: an id passed as ``None``."""
        await wired.run(*_journey())
        assert consumer.args_of("start_edr_negotiation")["target"] == _ASSET_ID

    async def test_the_negotiation_is_what_the_transfer_collects(
        self, wired: Harness, consumer: ConsumerDouble
    ) -> None:
        await wired.run(*_journey())
        assert consumer.args_of("get_edr_entry")["negotiation_id"] == "neg-1"

    async def test_the_transfer_settles_before_the_data_plane_is_called(
        self, wired: Harness
    ) -> None:
        outcome = await wired.run(*_journey())
        assert outcome.variables["state"] == "STARTED"
        assert outcome.variables["transfer_id"] == "tp-1"

    async def test_the_edr_token_is_the_one_the_data_plane_receives(
        self, wired: Harness, http: HttpDouble
    ) -> None:
        """A token lost between the steps reads as an unauthenticated call."""
        await wired.run(*_journey())
        call = http.calls_to("GET", "/api/public")[0]
        assert call.headers["Authorization"] == "Bearer edr-token"


class TestTheJourneyWithoutExplicitWiring:
    """The same journey with the later hops left to their fallbacks.

    Every step publishes its fields flatly as it runs, and most connector steps
    fall back to the context variable of the same name. So ``initiate_transfer``
    finds the ``negotiation_id`` and the data-plane step finds the
    ``dataplane_url``/``edr_token`` pair with nothing written down.

    ``negotiate`` is the exception, and it has its own class below.
    """

    @staticmethod
    def _implicit() -> list[dict]:
        steps = _journey()
        steps[3]["with"] = {}
        steps[4]["with"] = {"method": "GET", "path": "/api/public"}
        return steps

    async def test_the_implicit_chain_reaches_the_same_data(
        self, wired: Harness
    ) -> None:
        outcome = await wired.run(*self._implicit())
        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert outcome.output("pull") == {"shells": ["urn:uuid:1"]}

    async def test_the_transfer_finds_the_negotiation_by_itself(
        self, wired: Harness, consumer: ConsumerDouble
    ) -> None:
        await wired.run(*self._implicit())
        assert consumer.args_of("get_edr_entry")["negotiation_id"] == "neg-1"

    async def test_the_data_plane_finds_the_token_by_itself(
        self, wired: Harness, http: HttpDouble
    ) -> None:
        await wired.run(*self._implicit())
        call = http.calls_to("GET", "/api/public")[0]
        assert call.headers["Authorization"] == "Bearer edr-token"


class TestNegotiateDoesNotInheritFromExtractDataset:
    """``negotiate`` reads ``catalog_asset_id``, which ``extract_dataset`` never sets.

    The two steps name the same thing differently: ``extract_dataset``
    publishes ``asset_id`` and ``dataset``, while ``negotiate`` falls back to
    ``catalog_asset_id`` and ``catalog_policy`` — the pair
    ``query_catalog_by_asset_id`` publishes. Chaining catalog → extract →
    negotiate and leaving the negotiation's inputs out therefore negotiates for
    nothing, and the connector is the first thing to say so.

    That is survivable only because the IDE marks both parameters **required**
    on its ``negotiate`` block, so an authored TCK always writes them down.
    Pinned here so the day that changes, this fails.
    """

    async def test_leaving_the_asset_out_negotiates_for_nothing(
        self, wired: Harness, consumer: ConsumerDouble
    ) -> None:
        steps = _journey()
        steps[2]["with"] = {
            "counter_party_id": "BPNL000000000001",
            "counter_party_address": "https://provider/api/dsp",
            "poll_interval": 0,
        }

        await wired.run(*steps)

        assert consumer.args_of("start_edr_negotiation")["target"] is None

    async def test_the_extract_step_did_publish_it_under_its_own_name(
        self, wired: Harness
    ) -> None:
        """So the value is there — it is the name that does not match."""
        outcome = await wired.run(*_journey())
        assert outcome.variables["asset_id"] == _ASSET_ID
        assert "catalog_asset_id" not in outcome.variables


class TestAssertingAlongTheJourney:
    """Checks placed on the steps of a real chain, not on a stub output."""

    async def test_each_hop_can_be_asserted_where_it_happens(
        self, wired: Harness
    ) -> None:
        steps = _journey()
        steps[2]["validate"] = [
            {
                "uses": "validate/assert/equals",
                "with": {"input": "state", "value": "FINALIZED"},
            },
            {
                "uses": "validate/assert/not_null",
                "with": {"input": "agreement_id"},
            },
        ]
        steps[3]["validate"] = [
            {
                "uses": "validate/assert/matches_regex",
                "with": {"input": "dataplane_url", "value": r"^http://127\.0\.0\.1:\d+$"},
            },
        ]

        outcome = await wired.run(*steps)

        assert outcome.passed, outcome.assertion_messages("negotiate") + (
            outcome.assertion_messages("transfer")
        )

    async def test_a_check_on_a_later_hop_still_sees_the_earlier_values(
        self, wired: Harness
    ) -> None:
        steps = _journey()
        steps[4]["returns"] = {"value": {"type": "object"}}
        steps[4]["validate"] = [
            {
                "uses": "validate/field/length_equals",
                "with": {"input": "value", "path": "shells", "value": 1},
            }
        ]

        outcome = await wired.run(*steps)
        assert outcome.passed, outcome.assertion_messages("pull")


class TestWhenAHopProducesNothing:
    """A break in the chain surfaces where it breaks, not three steps later."""

    async def test_a_dct_type_that_matches_nothing_leaves_the_asset_unset(
        self, wired: Harness
    ) -> None:
        steps = _journey()
        steps[1]["with"]["dct_type"] = "cx-taxo:NoSuchThing"

        outcome = await wired.run(*steps)

        assert outcome.variables["asset_id"] is None
        assert outcome.variables["dataset"] is None

    async def test_the_break_is_catchable_by_an_assertion_at_the_hop(
        self, wired: Harness
    ) -> None:
        """Which is how a TCK author is meant to find it."""
        steps = _journey()
        steps[1]["with"]["dct_type"] = "cx-taxo:NoSuchThing"
        steps[1]["validate"] = [
            {"uses": "validate/assert/not_null", "with": {"input": "asset_id"}}
        ]

        outcome = await wired.run(*steps)

        assert not outcome.passed
        assert outcome.result("offer").status.value.lower() == "failed"


class TestTeardownDeletesWhatSetupMade:
    """A teardown step reads the id the setup phase published."""

    async def test_the_deleted_asset_is_the_one_that_was_created(
        self, wired: Harness
    ) -> None:
        provider: ProviderDouble = wired.context.services._by_type["CONNECTOR_PROVIDER"]

        await wired.run(
            {
                "id": "make_asset",
                "uses": "connector/provider/create_asset",
                "with": {"asset": {"asset_id": "asset-under-test", "base_url": "https://x"}},
                "returns": {"asset_id": {"type": "string"}},
            },
            phase="setup",
        )
        outcome = await wired.run(
            {
                "id": "drop_asset",
                "uses": "connector/provider/delete_asset",
                "with": {"asset_id": "${{ setup.make_asset.asset_id }}"},
                "returns": {"status_code": {"type": "integer"}},
            },
            phase="teardown",
        )

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert provider.assets.deleted == ["asset-under-test"]

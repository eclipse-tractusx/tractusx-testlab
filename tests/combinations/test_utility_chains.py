################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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

"""The small steps, chained the way a TCK chains them.

None of these do anything on their own: they take a value apart, put one
together, or turn one into another. Their whole purpose is to sit between two
steps that matter, so running them in isolation says the least about them.
"""

from __future__ import annotations

import pytest

from combinations.harness import Harness
from combinations.http_double import HttpDouble

pytestmark = pytest.mark.asyncio

#: An EDC ``subprotocolBody``, the string these steps most often meet.
SUBPROTOCOL = "dspEndpoint=https://provider.example/api/dsp;id=urn:uuid:asset-1"

#: A shell descriptor, shaped as the DTR returns one.
DESCRIPTOR = {
    "id": "urn:uuid:twin-1",
    "idShort": "gearbox",
    "specificAssetIds": [
        {"name": "manufacturerPartId", "value": "PART-9"},
        {"name": "partInstanceId", "value": "INST-3"},
    ],
    "submodelDescriptors": [
        {
            "id": "urn:uuid:sm-1",
            "endpoints": [
                {
                    "interface": "SUBMODEL-3.0",
                    "protocolInformation": {"subprotocolBody": SUBPROTOCOL},
                }
            ],
        }
    ],
}


class TestTakingAnEndpointApart:
    """The real reason ``util/parse_kv`` exists, run end to end."""

    async def test_the_asset_id_is_dug_out_of_a_descriptor_and_used(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/twins", DESCRIPTOR)
        http.json_route("GET", "/asset/urn:uuid:asset-1", {"found": True})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/twins"},
                "returns": {"response_body": {"type": "object"}},
            },
            {
                "id": "endpoint",
                "uses": "util/json_path_extract",
                "with": {
                    "input": "${{ execution.fetch.response_body }}",
                    "path": (
                        "submodelDescriptors.0.endpoints.0."
                        "protocolInformation.subprotocolBody"
                    ),
                },
                "returns": {"value": {"type": "string"}},
            },
            {
                "id": "asset",
                "uses": "util/parse_kv",
                "with": {"input": "${{ execution.endpoint.value }}", "select": "id"},
                "returns": {"value": {"type": "string"}},
            },
            {
                "id": "lookup",
                "uses": "http/http_request",
                "with": {
                    "method": "GET",
                    "url": f"{base}/asset/${{{{ execution.asset.value }}}}",
                },
            },
        )

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert http.calls_to("GET", "/asset/urn:uuid:asset-1")

    async def test_a_key_that_is_not_there_fails_where_it_is_read(
        self, harness: Harness
    ) -> None:
        """Not three steps later, as an empty URL."""
        outcome = await harness.run(
            {
                "id": "asset",
                "uses": "util/parse_kv",
                "with": {"input": SUBPROTOCOL, "select": "assetId"},
            },
        )

        assert not outcome.passed
        error = outcome.error("asset") or ""
        assert "assetId" in error and "id" in error

    async def test_the_whole_mapping_is_readable_when_no_key_is_selected(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "parse",
                "uses": "util/parse_kv",
                "with": {"input": SUBPROTOCOL},
                "returns": {"value": {"type": "object"}},
            },
            {
                "id": "endpoint",
                "uses": "util/json_path_extract",
                "with": {
                    "input": "${{ execution.parse.value }}",
                    "path": "dspEndpoint",
                },
            },
        )

        assert outcome.output("endpoint") == "https://provider.example/api/dsp"


class TestSelectingByPredicate:
    """A path may name an element by a property instead of an index."""

    async def test_a_specific_asset_id_is_found_by_its_name(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "part",
                "uses": "util/json_path_extract",
                "with": {
                    "input": DESCRIPTOR,
                    "path": "specificAssetIds[name=manufacturerPartId].value",
                },
            },
        )
        assert outcome.output("part") == "PART-9"

    async def test_a_submodel_is_found_by_its_interface(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "endpoint",
                "uses": "util/json_path_extract",
                "with": {
                    "input": DESCRIPTOR,
                    "path": (
                        "submodelDescriptors.0.endpoints[interface='SUBMODEL-3.0']."
                        "protocolInformation.subprotocolBody"
                    ),
                },
            },
        )
        assert outcome.output("endpoint") == SUBPROTOCOL


class TestEncodingAndBack:
    """``util/base64`` both ways, over a value another step produced."""

    async def test_a_value_survives_a_round_trip(self, harness: Harness) -> None:
        outcome = await harness.run(
            {
                "id": "mint",
                "uses": "util/generate_bpn",
                "returns": {"bpn": {"type": "string"}},
            },
            {
                "id": "encode",
                "uses": "util/base64",
                "with": {"input": "${{ execution.mint.bpn }}", "mode": "encode"},
                "returns": {"value": {"type": "string"}},
            },
            {
                "id": "decode",
                "uses": "util/base64",
                "with": {"input": "${{ execution.encode.value }}", "mode": "decode"},
            },
        )

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert outcome.output("decode") == outcome.output("mint")["bpn"]

    async def test_an_encoded_id_is_what_the_url_carries(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """DTR shell lookups take a base64url identifier, so this is the real use."""
        encoded = "dXJuOnV1aWQ6dHdpbi0x"
        http.json_route("GET", f"/shells/{encoded}", DESCRIPTOR)
        base = http.start()

        outcome = await harness.run(
            {
                "id": "encode",
                "uses": "util/base64",
                "with": {
                    "input": "urn:uuid:twin-1",
                    "mode": "encode",
                    "url_safe": True,
                    "strip_padding": True,
                },
                "returns": {"value": {"type": "string"}},
            },
            {
                "id": "shell",
                "uses": "http/http_request",
                "with": {
                    "method": "GET",
                    "url": f"{base}/shells/${{{{ execution.encode.value }}}}",
                },
                "returns": {"status_code": {"type": "integer"}},
            },
        )

        assert outcome.variables["status_code"] == 200


class TestCheckingAPathExists:
    """``util/validate_path`` fails the step; an assertion reports on it."""

    async def test_a_missing_path_fails_the_step_it_is_on(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "check",
                "uses": "util/validate_path",
                "with": {"input": DESCRIPTOR, "path": "globalAssetId"},
            },
        )
        assert not outcome.passed

    async def test_a_present_path_publishes_the_value_it_found(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "check",
                "uses": "util/validate_path",
                "with": {"input": DESCRIPTOR, "path": "idShort"},
                "returns": {"value": {"type": "string"}},
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.check.value }}"},
            },
        )

        assert outcome.passed, [(r.step_name, r.error) for r in outcome.failures]
        assert outcome.output("echo") == "gearbox"


class TestStoringUnderAChosenName:
    """``store_in_variable`` puts the result somewhere a later step names."""

    async def test_the_chosen_name_is_readable_downstream(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "asset",
                "uses": "util/parse_kv",
                "with": {
                    "input": SUBPROTOCOL,
                    "select": "id",
                    "store_in_variable": "provider_asset_id",
                },
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ env.provider_asset_id }}"},
            },
        )

        assert outcome.output("echo") == "urn:uuid:asset-1"

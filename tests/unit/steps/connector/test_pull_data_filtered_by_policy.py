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

"""Tests for connector/consumer/pull_data_filtered_by_policy."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from tractusx_sdk.dataspace.tools import PolicyMismatchError as SdkPolicyMismatchError

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps.connector.policy_mismatch import PolicyMismatchError
from tractusx_testlab.steps.connector.pull_data import ConnectorPullDataFilteredByPolicy


@pytest.fixture()
def consumer() -> MagicMock:
    svc = MagicMock()
    svc.get_catalog_with_filter.return_value = {
        "dataset": [{"@id": "asset-1"}],
        "participantId": "BPNL_PROVIDER",
    }
    svc.get_transfer_id.return_value = "transfer-1"
    svc.get_endpoint_with_token.return_value = ("http://dataplane.example", "token-abc")
    svc.dataspace_version = "jupiter"
    svc.get_filter_expression.return_value = {
        "operandLeft": "transferProcessId",
        "operator": "=",
        "operandRight": "transfer-1",
    }
    # The EDR entry is where the negotiation and the agreement behind a
    # transfer are named — the step reads its ids off exactly this document.
    svc.edrs.query.return_value = _Response(
        [
            {
                "transferProcessId": "transfer-1",
                "contractNegotiationId": "negotiation-1",
                "agreementId": "agreement-1",
            }
        ]
    )
    return svc


class _Response:
    """The bare shape of the ``requests.Response`` the EDR controller returns."""

    def __init__(self, body: list) -> None:
        self.status_code = 200
        self._body = body

    def json(self) -> list:
        return self._body


@pytest.fixture()
def context(consumer: MagicMock) -> StepContext:
    ctx = StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())
    # The connector is seeded into the run, so the step finds it by type rather
    # than by a name it was handed.
    ctx.services.service_names = ["connector"]
    ctx.services.get.return_value = consumer
    return ctx


def _definition() -> StepDefinition:
    return StepDefinition(id="pull", uses="connector/consumer/pull_data_filtered_by_policy")


class TestPullDataFilteredByPolicy:
    @pytest.mark.asyncio
    async def test_requires_policies(self, context: StepContext) -> None:
        with pytest.raises(
            ValueError, match="expected_policies: required key 'expected_policies' is missing"
        ):
            await ConnectorPullDataFilteredByPolicy().invoke(
                {
                    "counter_party_id": "BPNL_PROVIDER",
                    "counter_party_address": "https://provider.example/dsp",
                    "filters": [],
                },
                context,
                _definition(),
            )

    @pytest.mark.asyncio
    async def test_returns_edr_and_dataplane_url(
        self, context: StepContext, consumer: MagicMock
    ) -> None:
        output = await ConnectorPullDataFilteredByPolicy().invoke(
            {
                "counter_party_id": "BPNL_PROVIDER",
                "counter_party_address": "https://provider.example/dsp",
                "filters": [],
                "expected_policies": [{"permission": [{"action": "use"}]}],
            },
            context,
            _definition(),
        )
        assert output.value["edr_token"] == "token-abc"
        assert output.value["dataplane_url"] == "http://dataplane.example"
        assert output.value["transfer_id"] == "transfer-1"
        assert output.value["agreement_id"] == "agreement-1"
        assert output.value["negotiation_id"] == "negotiation-1"
        assert output.value["asset_id"] == "asset-1"

    @pytest.mark.asyncio
    async def test_normalizes_simplified_policy_keys(
        self, context: StepContext, consumer: MagicMock
    ) -> None:
        await ConnectorPullDataFilteredByPolicy().invoke(
            {
                "counter_party_id": "BPNL_PROVIDER",
                "counter_party_address": "https://provider.example/dsp",
                "filters": [],
                "expected_policies": [{"permissions": [{"action": "use", "constraints": []}]}],
            },
            context,
            _definition(),
        )
        forwarded_policies = consumer.get_transfer_id.call_args.kwargs["policies"]
        assert forwarded_policies == [{"permission": [{"action": "use", "constraint": []}]}]

    @pytest.mark.asyncio
    async def test_accepts_single_policy_dict(
        self, context: StepContext, consumer: MagicMock
    ) -> None:
        await ConnectorPullDataFilteredByPolicy().invoke(
            {
                "counter_party_id": "BPNL_PROVIDER",
                "counter_party_address": "https://provider.example/dsp",
                "filters": [],
                "expected_policies": {"permission": [{"action": "use"}]},
            },
            context,
            _definition(),
        )
        forwarded_policies = consumer.get_transfer_id.call_args.kwargs["policies"]
        assert forwarded_policies == [{"permission": [{"action": "use"}]}]

    @pytest.mark.asyncio
    async def test_a_rejected_offer_reports_the_constraint_that_rejected_it(
        self, context: StepContext, consumer: MagicMock
    ) -> None:
        """The step's verdict names the offers, not just that none was accepted."""
        offered = {
            "@id": "offer-1",
            "permission": [
                {
                    "action": "use",
                    "constraint": [
                        {
                            "and": [
                                {
                                    "leftOperand": "FrameworkAgreement",
                                    "operator": "eq",
                                    "rightOperand": "DataExchangeGovernance:1.0",
                                },
                                {
                                    "leftOperand": "Membership",
                                    "operator": "eq",
                                    "rightOperand": "active",
                                },
                            ]
                        }
                    ],
                }
            ],
        }
        expected = {
            "permission": [
                {
                    "action": "use",
                    "constraint": [
                        {
                            "leftOperand": "FrameworkAgreement",
                            "operator": "eq",
                            "rightOperand": "DataExchangeGovernance:1.0",
                        }
                    ],
                }
            ]
        }
        catalog = {"dataset": [{"@id": "asset-1", "hasPolicy": [offered]}]}
        cause = SdkPolicyMismatchError(
            "No valid policy was found for any item in the list. No valid asset found!",
            catalog=catalog,
            allowed_policies=[expected],
        )
        failure = RuntimeError(
            "[Connector Service]: [https://provider.example/dsp] It was not possible "
            "to find a valid policy in the catalog!"
        )
        failure.__cause__ = cause
        consumer.get_transfer_id.side_effect = failure

        with pytest.raises(PolicyMismatchError) as raised:
            await ConnectorPullDataFilteredByPolicy().invoke(
                {
                    "counter_party_id": "BPNL_PROVIDER",
                    "counter_party_address": "https://provider.example/dsp",
                    "filters": [],
                    "expected_policies": [expected],
                },
                context,
                _definition(),
            )

        assert "Membership eq active" in str(raised.value)
        assert raised.value.code == "POLICY_MISMATCH"
        assert raised.value.diagnostics["offers"][0]["asset_id"] == "asset-1"

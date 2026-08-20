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

"""Tests for the policy a consumer-side connector step is given."""

from __future__ import annotations

import json

import pytest

from tractusx_testlab.steps.connector.catalog_query import QueryCatalogByAssetIdParams
from tractusx_testlab.steps.connector.do_dsp import (
    DiscoverDtrAuthParams,
    DoDspParams,
    DoDspWithBpnlParams,
)
from tractusx_testlab.steps.connector.negotiate import NegotiateParams
from tractusx_testlab.steps.connector.policies import (
    as_odrl_policy,
    as_policy_list,
    as_raw_policy,
)
from tractusx_testlab.steps.connector.pull_data import (
    PullDataFilteredByPolicyParams,
    PullDataFilteredParams,
)

#: The raw ODRL document the SDK's offer comparison takes.
RAW = {"permission": [{"action": "use", "constraint": [{"leftOperand": "a"}]}]}

#: The same policy in the testlab simplified spelling.
SIMPLIFIED = {"permissions": [{"action": "use", "constraints": [{"left_operand": "a"}]}]}


class TestAsRawPolicy:
    def test_a_raw_policy_is_left_alone(self) -> None:
        assert as_raw_policy(RAW) == RAW

    def test_the_variable_that_holds_a_policy_is_unwrapped(self) -> None:
        assert as_raw_policy({"policy": RAW}) == RAW

    def test_json_text_is_the_policy_it_spells(self) -> None:
        assert as_raw_policy(json.dumps(RAW)) == RAW

    def test_a_variable_holding_json_text_is_both_unwrapped_and_parsed(self) -> None:
        assert as_raw_policy({"policy": json.dumps(RAW)}) == RAW

    def test_text_that_is_not_json_is_refused(self) -> None:
        with pytest.raises(ValueError, match="must be JSON"):
            as_raw_policy("a usage policy")


class TestAsPolicyList:
    def test_one_policy_becomes_a_list_of_one(self) -> None:
        assert as_policy_list(RAW) == [RAW]

    def test_no_policy_stays_absent(self) -> None:
        assert as_policy_list(None) is None

    def test_each_policy_of_a_list_is_unwrapped(self) -> None:
        assert as_policy_list([{"policy": RAW}, RAW]) == [RAW, RAW]

    def test_the_simplified_spelling_is_translated_to_odrl(self) -> None:
        assert as_policy_list(SIMPLIFIED) == [RAW]

    def test_a_wrapped_simplified_policy_is_both_unwrapped_and_translated(self) -> None:
        assert as_policy_list({"policy": SIMPLIFIED}) == [RAW]


class TestAsOdrlPolicy:
    def test_a_policy_already_in_odrl_is_unchanged(self) -> None:
        assert as_odrl_policy(RAW) == RAW

    def test_the_plural_rule_keys_and_snake_case_operands_are_renamed(self) -> None:
        assert as_odrl_policy(
            {"prohibitions": [{"constraints": [{"right_operand": "b"}]}], "obligations": []}
        ) == {"prohibition": [{"constraint": [{"rightOperand": "b"}]}], "obligation": []}


class TestEveryStepThatFiltersByPolicy:
    @pytest.mark.parametrize(
        ("params_cls", "required"),
        [
            (PullDataFilteredParams, {}),
            (PullDataFilteredByPolicyParams, {}),
            (DoDspParams, {}),
            (DoDspWithBpnlParams, {"bpnl": "BPNL_PROVIDER"}),
            (DiscoverDtrAuthParams, {}),
        ],
    )
    def test_reads_the_policy_out_of_the_variable_that_holds_it(
        self, params_cls: type, required: dict
    ) -> None:
        params = params_cls(expected_policies={"policy": SIMPLIFIED}, **required)
        assert params.expected_policies == [RAW]

    @pytest.mark.parametrize(
        ("params_cls", "required"),
        [(PullDataFilteredParams, {}), (DoDspWithBpnlParams, {"bpnl": "BPNL_PROVIDER"})],
    )
    def test_an_omitted_policy_stays_no_preference(self, params_cls: type, required: dict) -> None:
        assert params_cls(**required).expected_policies is None

    def test_a_policy_is_required_where_the_step_declares_it_so(self) -> None:
        with pytest.raises(ValueError, match="expected_policies"):
            PullDataFilteredByPolicyParams()

    def test_a_catalog_query_does_not_filter_by_policy_at_all(self) -> None:
        """Querying a catalog and choosing an offer from it are two different steps.

        The key is rejected rather than ignored, so a script carrying it from
        before the split is corrected instead of quietly losing the filter it
        thinks it still has.
        """
        assert "expected_policies" not in QueryCatalogByAssetIdParams.model_fields
        with pytest.raises(ValueError, match="expected_policies"):
            QueryCatalogByAssetIdParams(
                asset_id="asset-1",
                counter_party_id="BPNL_PROVIDER",
                counter_party_address="https://provider.example/dsp",
                expected_policies={"policy": SIMPLIFIED},
            )


class TestNegotiateReadsTheSamePolicy:
    def test_the_variable_that_holds_the_policy_is_unwrapped(self) -> None:
        assert NegotiateParams(policy={"policy": RAW}).policy == RAW

    def test_no_policy_falls_through_to_the_catalog_variable(self) -> None:
        assert NegotiateParams().policy is None

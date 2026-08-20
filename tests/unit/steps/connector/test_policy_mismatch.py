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

"""A rejected catalog offer says which constraint separated it from the expectation."""

from __future__ import annotations

from typing import Any

import pytest
from tractusx_sdk.dataspace.tools import DspTools
from tractusx_sdk.dataspace.tools import PolicyMismatchError as SdkPolicyMismatchError

from tractusx_testlab.steps.connector import policy_mismatch
from tractusx_testlab.steps.connector.policy_mismatch import PolicyMismatchError

#: The policy an ichub DTR asset is really offered under: three conditions,
#: ``and``-ed, under one permission.
PROVIDER_POLICY: dict[str, Any] = {
    "@id": "offer-1",
    "@type": "Offer",
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
                        {
                            "leftOperand": "UsagePurpose",
                            "operator": "isAnyOf",
                            "rightOperand": "cx.core.digitalTwinRegistry:1",
                        },
                    ]
                }
            ],
        }
    ],
}

#: What the script expected: the same policy without ``Membership``.
EXPECTED_POLICY: dict[str, Any] = {
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
                            "leftOperand": "UsagePurpose",
                            "operator": "isAnyOf",
                            "rightOperand": "cx.core.digitalTwinRegistry:1",
                        },
                    ]
                }
            ],
        }
    ],
    "prohibition": [],
    "obligation": [],
}

CATALOG: dict[str, Any] = {
    "@type": "Catalog",
    "dataset": [{"@id": "asset-dtr", "@type": "Dataset", "hasPolicy": [PROVIDER_POLICY]}],
}


def _sdk_failure(catalog: dict | None, allowed: list | None) -> RuntimeError:
    """The failure the SDK raises, as it reaches a step: wrapped, cause attached."""
    cause = SdkPolicyMismatchError(
        "No valid policy was found for any item in the list. No valid asset found!",
        catalog=catalog,
        allowed_policies=allowed,
    )
    wrapped = RuntimeError(
        "[Connector Service]: [https://provider.example/dsp] It was not possible to "
        f"find a valid policy in the catalog! Reason: [{cause}]"
    )
    wrapped.__cause__ = cause
    return wrapped


class TestReadingAPolicy:
    def test_the_conditions_are_read_out_of_the_and_nesting(self) -> None:
        constraints = policy_mismatch.constraints_of(PROVIDER_POLICY)
        assert [str(item) for item in constraints] == [
            "FrameworkAgreement eq DataExchangeGovernance:1.0",
            "Membership eq active",
            "UsagePurpose isAnyOf cx.core.digitalTwinRegistry:1",
        ]

    def test_the_prefixed_dialect_says_the_same_thing(self) -> None:
        """A legacy connector spells every key with its namespace; same policy."""
        legacy = {
            "odrl:permission": {
                "odrl:constraint": {
                    "odrl:and": [
                        {
                            "odrl:leftOperand": {"@id": "Membership"},
                            "odrl:operator": {"@id": "odrl:eq"},
                            "odrl:rightOperand": "active",
                        }
                    ]
                }
            }
        }
        assert [str(item) for item in policy_mismatch.constraints_of(legacy)] == [
            "Membership odrl:eq active"
        ]

    def test_a_rule_kind_is_part_of_the_condition(self) -> None:
        """The same condition permitted and prohibited are opposite requirements."""
        permitted = policy_mismatch.constraints_of(
            {
                "permission": {
                    "constraint": {"leftOperand": "X", "operator": "eq", "rightOperand": "1"}
                }
            }
        )
        prohibited = policy_mismatch.constraints_of(
            {
                "prohibition": {
                    "constraint": {"leftOperand": "X", "operator": "eq", "rightOperand": "1"}
                }
            }
        )
        assert permitted != prohibited
        assert prohibited[0].described() == "prohibition: X eq 1"

    def test_a_list_of_accepted_values_is_read_whole(self) -> None:
        constraints = policy_mismatch.constraints_of(
            {
                "permission": {
                    "constraint": {
                        "leftOperand": "UsagePurpose",
                        "operator": "isAnyOf",
                        "rightOperand": ["cx.core.industrycore:1", "cx.core.digitalTwinRegistry:1"],
                    }
                }
            }
        )
        assert str(constraints[0]) == (
            "UsagePurpose isAnyOf cx.core.industrycore:1, cx.core.digitalTwinRegistry:1"
        )


class TestComparingOffers:
    def test_the_extra_condition_the_provider_requires_is_named(self) -> None:
        (comparison,) = policy_mismatch.compare(CATALOG, [EXPECTED_POLICY])
        assert comparison.asset_id == "asset-dtr"
        assert [str(item) for item in comparison.offered_not_expected] == ["Membership eq active"]
        assert comparison.expected_not_offered == ()

    def test_the_condition_the_provider_omits_is_named_too(self) -> None:
        stricter = {
            "permission": {
                "constraint": {
                    "and": [
                        {
                            "leftOperand": "FrameworkAgreement",
                            "operator": "eq",
                            "rightOperand": "DataExchangeGovernance:1.0",
                        },
                        {"leftOperand": "Membership", "operator": "eq", "rightOperand": "active"},
                        {
                            "leftOperand": "UsagePurpose",
                            "operator": "isAnyOf",
                            "rightOperand": "cx.core.digitalTwinRegistry:1",
                        },
                        {"leftOperand": "Dismantler", "operator": "eq", "rightOperand": "active"},
                    ]
                }
            }
        }
        (comparison,) = policy_mismatch.compare(CATALOG, [stricter])
        assert [str(item) for item in comparison.expected_not_offered] == ["Dismantler eq active"]

    def test_an_offer_is_measured_against_the_expectation_it_is_closest_to(self) -> None:
        """A script naming alternatives asks which one the provider came nearest to."""
        far = {
            "permission": {
                "constraint": {"leftOperand": "A", "operator": "eq", "rightOperand": "1"}
            }
        }
        (comparison,) = policy_mismatch.compare(CATALOG, [far, EXPECTED_POLICY])
        assert comparison.expected_index == 1

    def test_every_offer_in_the_catalog_is_compared(self) -> None:
        catalog = {
            "dataset": [
                {"@id": "asset-a", "hasPolicy": [PROVIDER_POLICY]},
                {"@id": "asset-b", "hasPolicy": PROVIDER_POLICY},
            ]
        }
        comparisons = policy_mismatch.compare(catalog, [EXPECTED_POLICY])
        assert [item.asset_id for item in comparisons] == ["asset-a", "asset-b"]


class TestExplainingTheFailure:
    def test_the_verdict_is_replaced_by_the_comparison_behind_it(self) -> None:
        with pytest.raises(PolicyMismatchError) as raised:
            with policy_mismatch.explained("https://provider.example/dsp"):
                raise _sdk_failure(CATALOG, [EXPECTED_POLICY])

        error = raised.value
        assert "Membership eq active" in str(error)
        assert "https://provider.example/dsp" in str(error)
        assert error.code == "POLICY_MISMATCH"
        assert error.diagnostics["offers_compared"] == 1
        assert error.diagnostics["offers"][0]["offered_not_expected"] == ["Membership eq active"]
        assert error.diagnostics["expected_policies"] == [
            [
                "FrameworkAgreement eq DataExchangeGovernance:1.0",
                "UsagePurpose isAnyOf cx.core.digitalTwinRegistry:1",
            ]
        ]

    def test_the_sdk_message_is_kept_as_the_cause(self) -> None:
        with pytest.raises(PolicyMismatchError) as raised:
            with policy_mismatch.explained("https://provider.example/dsp"):
                raise _sdk_failure(CATALOG, [EXPECTED_POLICY])

        assert "It was not possible to find a valid policy" in str(raised.value.__cause__)

    def test_an_empty_allow_list_is_named_as_the_cause(self) -> None:
        """``expected_policies: []`` rejects every offer before comparing anything."""
        with pytest.raises(PolicyMismatchError) as raised:
            with policy_mismatch.explained("https://provider.example/dsp"):
                raise _sdk_failure(CATALOG, [])

        assert "empty list" in str(raised.value)

    def test_another_failure_of_the_flow_is_left_alone(self) -> None:
        """A negotiation that never finalised is not about the policy."""
        with pytest.raises(RuntimeError, match="did not reach FINALIZED") as raised:
            with policy_mismatch.explained("https://provider.example/dsp"):
                raise RuntimeError("[Connector Service]: The EDR did not reach FINALIZED state")

        assert not isinstance(raised.value, PolicyMismatchError)

    def test_a_catalog_with_nothing_to_compare_keeps_the_sdk_message(self) -> None:
        """No offer was read: the provider published nothing, which it already says."""
        with pytest.raises(RuntimeError) as raised:
            with policy_mismatch.explained("https://provider.example/dsp"):
                raise _sdk_failure({"dataset": []}, [EXPECTED_POLICY])

        assert not isinstance(raised.value, PolicyMismatchError)


class TestAgainstTheSdk:
    def test_the_sdk_really_rejects_what_this_explains(self) -> None:
        """The explanation is only ever of a match the SDK itself refused.

        Guards the seam: if the SDK ever accepted an offer with a constraint the
        script did not ask for, this module would be explaining a failure that
        no longer happens.
        """
        with pytest.raises(SdkPolicyMismatchError) as raised:
            DspTools.filter_assets_and_policies(catalog=CATALOG, allowed_policies=[EXPECTED_POLICY])
        assert raised.value.catalog is CATALOG
        assert raised.value.allowed_policies == [EXPECTED_POLICY]

    def test_the_sdk_accepts_the_policy_it_was_offered(self) -> None:
        matched = DspTools.filter_assets_and_policies(
            catalog=CATALOG, allowed_policies=[PROVIDER_POLICY]
        )
        assert matched == [("asset-dtr", PROVIDER_POLICY)]

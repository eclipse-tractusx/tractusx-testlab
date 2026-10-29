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

"""No filter, no negotiation: the steps that pick an offer refuse to pick blindly."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.do_dsp import DoDspStep, DoDspWithBpnlStep
from tractusx_testlab.steps.connector.offer_guard import AnyOfferRefusedError
from tractusx_testlab.steps.connector.pull_data import (
    ConnectorPullDataFiltered,
    ConnectorPullDataFilteredByPolicy,
)

_POLICY = [{"permission": [{"action": "use"}]}]
_STEPS = [
    (
        ConnectorPullDataFiltered,
        {"counter_party_id": "BPNL1", "counter_party_address": "https://p/dsp"},
    ),
    (
        ConnectorPullDataFilteredByPolicy,
        {
            "counter_party_id": "BPNL1",
            "counter_party_address": "https://p/dsp",
            "expected_policies": _POLICY,
        },
    ),
    (DoDspStep, {"counter_party_id": "BPNL1", "counter_party_address": "https://p/dsp"}),
    (DoDspWithBpnlStep, {"bpnl": "BPNL1"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("step_cls", "params"), _STEPS)
@pytest.mark.parametrize("filters", [None, []])
async def test_a_step_without_filters_is_refused_before_the_catalog_is_asked(
    step_cls: type, params: dict, filters: list | None, mock_context: MagicMock
) -> None:
    raw = {**params, **({} if filters is None else {"filters": filters})}
    with pytest.raises(AnyOfferRefusedError) as refused:
        await step_cls().invoke(raw, mock_context, StepDefinition(uses=step_cls.step_type))
    assert refused.value.code == "OFFER_FILTER_MISSING"
    assert "allow_any_offer: true" in str(refused.value)
    mock_context.dataspace.consumer.return_value.get_catalog_with_filter.assert_not_called()
    mock_context.dataspace.consumer.return_value.do_dsp.assert_not_called()


@pytest.mark.parametrize(("step_cls", "params"), _STEPS)
def test_filters_or_the_opt_out_pass_the_guard(step_cls: type, params: dict) -> None:
    with_filter = step_cls.params_model.model_validate(
        {**params, "filters": [{"operand_left": "id", "operand_right": "a"}]}
    )
    with_filter.require_offer_filter()
    step_cls.params_model.model_validate({**params, "allow_any_offer": True}).require_offer_filter()


def test_the_refusal_is_the_authors_not_the_suts() -> None:
    assert AnyOfferRefusedError().origin == "authoring"

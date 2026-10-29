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

"""A negotiating step without filters is warned at compile time."""

from __future__ import annotations

import pytest

from tractusx_testlab.compiler.validation.validator import TestValidator
from tractusx_testlab.models import TestDefinition

_FILTER = [{"operand_left": "https://w3id.org/edc/v0.0.1/ns/id", "operand_right": "asset-1"}]


def _warnings(with_: dict | None, uses: str) -> list[str]:
    test = TestDefinition.model_validate(
        {
            "syntax": "v1-alpha",
            "kind": "test",
            "id": "t",
            "namespace": "n",
            "metadata": {"name": "t"},
            "execution": [
                {"id": "pull", "uses": uses, **({"with": with_} if with_ is not None else {})}
            ],
        }
    )
    return [i.message for i in TestValidator().validate(test).issues if i.level == "warning"]


_GUARDED = [
    "connector/consumer/pull_data_filtered",
    "connector/consumer/pull_data_filtered_by_policy",
    "connector/consumer/do_dsp",
    "connector/consumer/do_dsp_with_bpnl",
]


@pytest.mark.parametrize("uses", _GUARDED)
@pytest.mark.parametrize("with_", [None, {}, {"filters": []}])
def test_no_filters_is_warned(uses: str, with_: dict | None) -> None:
    (warning,) = _warnings(with_, uses)
    assert "no 'filters'" in warning and "allow_any_offer: true" in warning


@pytest.mark.parametrize("uses", _GUARDED)
def test_filters_or_the_opt_out_are_not_warned(uses: str) -> None:
    assert _warnings({"filters": _FILTER}, uses) == []
    assert _warnings({"allow_any_offer": True}, uses) == []


def test_a_catalog_query_without_filters_is_not_warned() -> None:
    assert _warnings({}, "connector/consumer/query_catalog_with_filters") == []

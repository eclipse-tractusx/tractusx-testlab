#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""Tests for path extraction — list traversal and ``[key=value]`` predicates.

The digital-twin shell descriptor is the motivating shape: two nested arrays
(``submodelDescriptors`` → ``endpoints``) and predicate values containing dots
(``SUBMODEL-VALUE-3.1``, semantic IDs).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.steps._checks.extraction import _split_path, extract_path
from tractusx_testlab.steps.base import StepOutput
from tractusx_testlab.steps.utility.json_extract import JsonPathExtractStep

_HREF = "https://dataplane.example/value/sm-2"

# idShort values are deliberately arbitrary: a test must not depend on knowing
# them, and the target descriptor is not the first entry.
SHELL_DESCRIPTOR = {
    "id": "urn:uuid:shell-1",
    "idShort": "vehicle",
    "submodelDescriptors": [
        {
            "id": "sm-1",
            "idShort": "WhateverName123",
            "endpoints": [
                {
                    "interface": "SUBMODEL-3.0",
                    "protocolInformation": {"href": "https://dataplane.example/legacy"},
                },
            ],
        },
        {
            "id": "sm-2",
            "idShort": "another_arbitrary_id",
            "semanticId": {
                "type": "ExternalReference",
                "keys": [
                    {
                        "type": "GlobalReference",
                        "value": "urn:samm:io.catenax.pap:1.0.0#PartAsPlanned",
                    },
                ],
            },
            "endpoints": [
                {
                    "interface": "AAS-3.0",
                    "protocolInformation": {"href": "https://dataplane.example/aas"},
                },
                {
                    "interface": "SUBMODEL-VALUE-3.1",
                    "protocolInformation": {"href": _HREF},
                },
            ],
        },
    ],
}

# The path a real test uses: it names no idShort and no index.
_HREF_PATH = (
    "submodelDescriptors.endpoints[interface='SUBMODEL-VALUE-3.1']"
    ".protocolInformation.href"
)


class TestSplitPath:
    """Dots inside ``[...]`` predicates must not act as separators."""

    def test_plain_path_splits_on_dots(self) -> None:
        assert _split_path("a.b.c") == ["a", "b", "c"]

    def test_dots_inside_predicate_are_preserved(self) -> None:
        assert _split_path("endpoints[interface='SUBMODEL-VALUE-3.1'].href") == [
            "endpoints[interface='SUBMODEL-VALUE-3.1']",
            "href",
        ]

    def test_semantic_id_predicate_survives(self) -> None:
        path = "descriptors[semanticId='urn:samm:io.catenax.bom:1.0.0#Bom'].id"
        assert _split_path(path) == [
            "descriptors[semanticId='urn:samm:io.catenax.bom:1.0.0#Bom']",
            "id",
        ]


class TestExtractPath:
    """extract_path must behave identically for a dict and a StepOutput."""

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            (_HREF_PATH, _HREF),
            ("submodelDescriptors.1.endpoints.1.protocolInformation.href", _HREF),
            ("submodelDescriptors.1.id", "sm-2"),
            # select a descriptor by a nested property, naming no idShort
            ("submodelDescriptors[endpoints.interface='SUBMODEL-VALUE-3.1'].id", "sm-2"),
            (
                "submodelDescriptors[semanticId.keys.value="
                "'urn:samm:io.catenax.pap:1.0.0#PartAsPlanned'].id",
                "sm-2",
            ),
            # a direct-key predicate still works
            ("submodelDescriptors[idShort=WhateverName123].id", "sm-1"),
        ],
    )
    def test_dict_and_step_output_agree(self, path: str, expected: str) -> None:
        assert extract_path(SHELL_DESCRIPTOR, path) == expected
        assert extract_path(StepOutput(value=SHELL_DESCRIPTOR), path) == expected

    def test_response_body_alias_then_list_index(self) -> None:
        output = StepOutput(value=SHELL_DESCRIPTOR)
        assert extract_path(output, "response_body.submodelDescriptors.1.id") == "sm-2"

    def test_non_matching_predicate_yields_none(self) -> None:
        descriptor_without_interface = {
            "submodelDescriptors": [
                {
                    "id": "sm-1",
                    "endpoints": [
                        {
                            "interface": "SUBMODEL-3.0",
                            "protocolInformation": {"href": "https://x/legacy"},
                        },
                    ],
                },
            ],
        }
        assert extract_path(StepOutput(value=descriptor_without_interface), _HREF_PATH) is None

    def test_whole_array_is_returned(self) -> None:
        result = extract_path(StepOutput(value=SHELL_DESCRIPTOR), "submodel_descriptors")
        assert isinstance(result, list)
        assert len(result) == 2


class TestJsonPathExtractPredicates:
    """json_path_extract shares the predicate syntax and raises when unmatched."""

    @pytest.fixture()
    def context(self) -> StepContext:
        ctx = StepContext(services=MagicMock(), job=MagicMock(), config=MagicMock())
        ctx.set_variable("dt_body", SHELL_DESCRIPTOR)
        return ctx

    @staticmethod
    def _definition() -> StepDefinition:
        return StepDefinition(id="get_href", uses="util/json_path_extract")

    @pytest.mark.asyncio
    async def test_extracts_href_via_nested_predicates(self, context: StepContext) -> None:
        output = await JsonPathExtractStep().invoke(
            {"input": "dt_body", "path": _HREF_PATH, "store_in_variable": "href"},
            context,
            self._definition(),
        )
        assert output.value == _HREF
        assert context.get_variable("href") == _HREF

    @pytest.mark.asyncio
    async def test_unmatched_predicate_raises_key_error(self, context: StepContext) -> None:
        path = "submodelDescriptors[idShort=Missing].id"
        with pytest.raises(KeyError, match="No element in 'submodelDescriptors'"):
            await JsonPathExtractStep().invoke(
                {"input": "dt_body", "path": path}, context, self._definition(),
            )

    @pytest.mark.asyncio
    async def test_source_may_be_resolved_object_not_only_a_name(
        self, context: StepContext,
    ) -> None:
        # A ``${{ }}`` expression resolves before the step runs, so ``source``
        # arrives as the dict itself rather than a variable name.  This must not
        # raise ``TypeError: unhashable type: dict``.
        output = await JsonPathExtractStep().invoke(
            {"input": SHELL_DESCRIPTOR, "path": _HREF_PATH},
            context,
            self._definition(),
        )
        assert output.value == _HREF

    @pytest.mark.asyncio
    async def test_missing_named_source_raises_key_error(self, context: StepContext) -> None:
        with pytest.raises(KeyError, match="Context variable 'nope' not found"):
            await JsonPathExtractStep().invoke(
                {"input": "nope", "path": "a"}, context, self._definition(),
            )

    @pytest.mark.asyncio
    async def test_numeric_index_still_works(self, context: StepContext) -> None:
        output = await JsonPathExtractStep().invoke(
            {"input": "dt_body", "path": "submodelDescriptors.0.idShort"},
            context,
            self._definition(),
        )
        assert output.value == "WhateverName123"

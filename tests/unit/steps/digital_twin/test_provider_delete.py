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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Contract tests for ``digital-twin/provider/delete_shell_descriptor``.

The step's whole output is the status the registry answered the delete with, so
these tests are about one question: can a TCK tell 204 from 404 by reading a
declared output rather than by digging through the HTTP record?
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.digital_twin.provider.shell import DeleteShellDescriptorStep

_AAS_URL = "https://dtr.example.com/api/v3"
_SHELL_ID = "urn:uuid:11111111-2222-3333-4444-555555555555"


def _definition() -> StepDefinition:
    return StepDefinition(
        id="delete_twin", uses="digital-twin/provider/delete_shell_descriptor"
    )


def _refusal(*codes: str | None) -> SimpleNamespace:
    """An AAS ``Result`` as the SDK hands one back when the registry refuses.

    Only the two attributes the step reads are modelled — the messages and the
    ``code`` on each — because a registry's refusal document is the AAS
    specification's shape, not testlab's.
    """
    return SimpleNamespace(messages=[SimpleNamespace(code=code) for code in codes])


@pytest.fixture()
def aas(mock_context: MagicMock) -> MagicMock:
    """The registry service the step deletes through."""
    service = MagicMock()
    service.aas_url = _AAS_URL
    mock_context.dataspace.registry.return_value = service
    return service


async def _delete(context: MagicMock) -> Any:
    return await DeleteShellDescriptorStep().invoke(
        raw_params={"aas_identifier": _SHELL_ID},
        context=context,
        definition=_definition(),
    )


class TestDeleteShellDescriptorStatusCode:
    """The step publishes ``status_code`` as its declared output."""

    @pytest.mark.asyncio
    async def test_a_registry_that_accepted_the_delete_reads_as_204(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        # Arrange — the SDK collapses an accepted delete to None
        aas.delete_asset_administration_shell_descriptor.return_value = None

        # Act
        output = await _delete(mock_context)

        # Assert
        assert output.value == {"status_code": 204}

    @pytest.mark.asyncio
    async def test_a_registry_that_had_no_such_twin_reads_as_404(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        """The distinction the step exists for: gone already is not deleted."""
        aas.delete_asset_administration_shell_descriptor.return_value = _refusal("404")

        output = await _delete(mock_context)

        assert output.value == {"status_code": 404}

    @pytest.mark.asyncio
    async def test_the_status_is_published_as_a_context_variable(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        """A declared output is published, so a later step can read it by name."""
        aas.delete_asset_administration_shell_descriptor.return_value = _refusal("404")

        await _delete(mock_context)

        assert mock_context.variables["status_code"] == 404

    @pytest.mark.asyncio
    async def test_a_refusal_naming_no_code_still_reports_a_refusal(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        """A registry that sends no usable code must not read as a success."""
        aas.delete_asset_administration_shell_descriptor.return_value = _refusal(None)

        output = await _delete(mock_context)

        assert output.value == {"status_code": 400}

    @pytest.mark.asyncio
    async def test_a_non_numeric_code_is_not_mistaken_for_a_status(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        """AAS lets ``code`` carry a vendor string; it is not an HTTP status."""
        aas.delete_asset_administration_shell_descriptor.return_value = _refusal(
            "ERR_NOT_FOUND"
        )

        output = await _delete(mock_context)

        assert output.value == {"status_code": 400}

    @pytest.mark.asyncio
    async def test_the_first_usable_code_wins_over_later_messages(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        aas.delete_asset_administration_shell_descriptor.return_value = _refusal(
            None, "403", "500"
        )

        output = await _delete(mock_context)

        assert output.value == {"status_code": 403}


class TestDeleteShellDescriptorHttpRecord:
    """The HTTP record agrees with the declared output."""

    @pytest.mark.asyncio
    async def test_the_response_status_matches_the_declared_output(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        aas.delete_asset_administration_shell_descriptor.return_value = _refusal("404")

        output = await _delete(mock_context)

        assert output.response.status_code == 404
        assert output.value["status_code"] == output.response.status_code

    @pytest.mark.asyncio
    async def test_the_request_names_the_shell_it_deleted(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        aas.delete_asset_administration_shell_descriptor.return_value = None

        output = await _delete(mock_context)

        assert output.request.method == "DELETE"
        assert output.request.url == f"{_AAS_URL}/shell-descriptors/{_SHELL_ID}"

    @pytest.mark.asyncio
    async def test_the_bpn_is_passed_through_to_the_registry(
        self, mock_context: MagicMock, aas: MagicMock
    ) -> None:
        aas.delete_asset_administration_shell_descriptor.return_value = None

        await DeleteShellDescriptorStep().invoke(
            raw_params={"aas_identifier": _SHELL_ID, "bpn": "BPNL000000000001"},
            context=mock_context,
            definition=_definition(),
        )

        aas.delete_asset_administration_shell_descriptor.assert_called_once_with(
            _SHELL_ID, bpn="BPNL000000000001"
        )

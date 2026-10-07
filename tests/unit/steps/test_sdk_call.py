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

"""A service that did not do its part is not TestLab reporting its own fault.

The SDK reports every one of them as a ``RuntimeError``, and the runner calls an
exception it does not recognise an engine fault. That is how *the provider did
not share any matching asset* reached the report as **TestLab reported this as
its own fault**. ``sdk_call.run`` is the one place every SDK call crosses, so it
is where the failure is named, and these hold the four answers apart.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tractusx_sdk.dataspace.services.connector import BaseConnectorConsumerService

from tractusx_testlab.models import BoundServiceError, ConnectorError
from tractusx_testlab.models.authoring.definitions import StepDefinition
from tractusx_testlab.models.primitives.enums import StepStatus
from tractusx_testlab.models.runtime.results import ENGINE_FAULT_PREFIX
from tractusx_testlab.player.execution.step_runner import run_step
from tractusx_testlab.steps import sdk_call
from tractusx_testlab.steps.http.request import HttpRequestStep

#: What the SUT's connector answered in the run that prompted this: the catalog
#: came back, and it carried nothing the step could negotiate.
NO_ASSET = (
    "[Connector Service]: [https://provider.example/api/v1/dsp] It was not possible to "
    "find a valid policy in the catalog! Reason: [No asset was found in the catalog! "
    "The provider did not share any matching asset.]"
)


class _Connector(BaseConnectorConsumerService):
    """A connector service in name only: bound methods, no adapters behind them."""

    def get_edr(self, **_: object) -> None:
        raise RuntimeError(NO_ASSET)

    def start_edr_negotiation(self, **_: object) -> None:
        raise TypeError("start_edr_negotiation() got an unexpected keyword argument")


def _connector() -> _Connector:
    return _Connector.__new__(_Connector)


def _definition() -> StepDefinition:
    return StepDefinition(
        uses="http/http_request",
        name="pull the data",
        with_={"url": "https://api.example.test/parts"},
    )


class TestNamingTheFailure:
    async def test_a_catalog_with_no_matching_asset_belongs_to_the_connector(self) -> None:
        """The verdict the report used to file as a bug against TestLab."""
        with pytest.raises(ConnectorError) as raised:
            await sdk_call.run(_connector().get_edr, transfer_id="t-1")

        assert str(raised.value) == NO_ASSET
        assert raised.value.code == "CONNECTOR_ERROR"
        assert raised.value.origin == "connector"

    async def test_the_sdk_message_is_kept_as_the_cause(self) -> None:
        """Nothing is lost by naming it: the SDK's sentence is one link down."""
        with pytest.raises(ConnectorError) as raised:
            await sdk_call.run(_connector().get_edr)

        assert isinstance(raised.value.__cause__, RuntimeError)
        assert str(raised.value.__cause__) == NO_ASSET

    async def test_a_service_with_no_two_ends_is_named_as_the_infrastructure(self) -> None:
        """A registry that would not answer is the deployment's, not TestLab's."""

        def blow_up(**_: object) -> None:
            raise RuntimeError("[DTR Service]: the registry answered 503")

        with pytest.raises(BoundServiceError) as raised:
            await sdk_call.run(blow_up, twin_id="urn:uuid:1")

        assert not isinstance(raised.value, ConnectorError)
        assert raised.value.code == "INFRASTRUCTURE_ERROR"
        assert raised.value.origin == "infrastructure"

    async def test_a_bug_of_ours_is_left_to_be_reported_as_one(self) -> None:
        """Only the SDK's failure channel is translated; a ``TypeError`` is ours."""
        with pytest.raises(TypeError):
            await sdk_call.run(_connector().start_edr_negotiation, wrong="kw")

    async def test_a_call_that_succeeds_returns_what_the_sdk_returned(self) -> None:
        def answer(**kwargs: object) -> dict[str, object]:
            return kwargs

        assert await sdk_call.run(answer, transfer_id="t-1") == {"transfer_id": "t-1"}

    def test_the_dataspace_exchange_is_one_of_those(self) -> None:
        """``connector`` is the infrastructure failure that has two ends."""
        assert issubclass(ConnectorError, BoundServiceError)


class TestWhatTheRunnerRecords:
    async def test_a_connector_failure_is_not_marked_an_engine_fault(
        self, mock_context: MagicMock
    ) -> None:
        """The origin the trace publishes, and the prefix it does not carry."""
        with patch.object(
            HttpRequestStep, "invoke", new_callable=AsyncMock, side_effect=ConnectorError(NO_ASSET)
        ):
            result = await run_step(HttpRequestStep, _definition(), "pull_data", mock_context)

        assert result.status == StepStatus.FAILED
        assert result.error == NO_ASSET
        assert not result.error.startswith(ENGINE_FAULT_PREFIX)
        assert result.error_code == "CONNECTOR_ERROR"
        assert result.error_origin == "connector"

    async def test_an_unrecognised_exception_is_still_an_engine_fault(
        self, mock_context: MagicMock
    ) -> None:
        """The classification that was right all along stays right."""
        with patch.object(
            HttpRequestStep, "invoke", new_callable=AsyncMock, side_effect=KeyError("policy")
        ):
            result = await run_step(HttpRequestStep, _definition(), "pull_data", mock_context)

        assert result.error is not None
        assert result.error.startswith(ENGINE_FAULT_PREFIX)
        assert result.error_origin == "engine"

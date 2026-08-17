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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Contract tests for the Digital Twin Registry steps."""

from __future__ import annotations

import base64
import json
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.base import StepOutput
from tractusx_testlab.steps.industry.dtr import (
    DataplaneGetShellDescriptorsStep,
    DataplaneGetShellDescriptorStep,
    DescriptorPayload,
    GetShellDescriptorStep,
    ProviderShellLookupParams,
    ProviderShellLookupStep,
    ShellLookupByAssetLinkParams,
    ShellLookupByAssetLinkStep,
    ShellLookupParams,
    ShellLookupStep,
)
from tractusx_testlab.syntax.context_vars import DATAPLANE_URL, EDR_TOKEN

_DATAPLANE = "https://provider.example.com/api/public"
_TOKEN = "Bearer eyJhbGciOiJSUzI1NiJ9.test"
_SHELL_ID = "urn:uuid:11111111-2222-3333-4444-555555555555"
_DESCRIPTOR = {"id": _SHELL_ID, "idShort": "twin-a", "specificAssetIds": []}


class _Response:
    def __init__(self, status_code: int = 200, body: Any = None) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self._body = body

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no body")
        return self._body


def _definition() -> StepDefinition:
    return StepDefinition(
        id="lookup", uses="digital-twin-registry/consumer/dataplane/lookup_shell"
    )


@pytest.fixture()
def context(mock_context: MagicMock) -> MagicMock:
    mock_context.config.default_timeout_s = 30
    return mock_context


def _params(**overrides: Any) -> dict:
    return {
        "specific_asset_ids": [{"name": "partInstanceId", "value": "SN-111"}],
        "dataplane_url": _DATAPLANE,
        "edr_token": _TOKEN,
        **overrides,
    }


def _responses(*bodies: Optional[_Response]) -> list:
    return list(bodies)


# ---------------------------------------------------------------------------
# C37 — one spelling on the way out
# ---------------------------------------------------------------------------


class TestDescriptorSerialisation:
    def test_the_aas_camel_case_is_accepted_on_the_way_in(self) -> None:
        assert DescriptorPayload.of(_DESCRIPTOR).id_short == "twin-a"

    def test_only_the_snake_case_spelling_is_written_on_the_way_out(self) -> None:
        output = GetShellDescriptorStep.bind_output(
            StepOutput(value=DescriptorPayload.of(_DESCRIPTOR))
        )
        assert output.value["id_short"] == "twin-a"
        assert "idShort" not in output.value

    def test_keys_the_registry_added_are_kept(self) -> None:
        output = GetShellDescriptorStep.bind_output(
            StepOutput(value=DescriptorPayload.of(_DESCRIPTOR))
        )
        assert output.value["specificAssetIds"] == []


# ---------------------------------------------------------------------------
# C04 / C27 — the consumer-side lookup
# ---------------------------------------------------------------------------


class TestAssetIdEncoding:
    def test_each_criterion_travels_base64url_encoded(self) -> None:
        params = ShellLookupParams.model_validate(_params())
        (encoded,) = params.asset_id_query()
        decoded = json.loads(base64.urlsafe_b64decode(encoded + "==").decode())
        assert decoded == {"name": "partInstanceId", "value": "SN-111"}

    def test_every_criterion_gets_its_own_value(self) -> None:
        params = ShellLookupParams.model_validate(
            _params(
                specific_asset_ids=[
                    {"name": "partInstanceId", "value": "SN-111"},
                    {"name": "manufacturerId", "value": "BPNL01"},
                ]
            )
        )
        assert len(params.asset_id_query()) == 2

    def test_a_criterion_the_aas_spec_adds_is_kept(self) -> None:
        """``externalSubjectId`` scopes a criterion to one partner."""
        params = ShellLookupParams.model_validate(
            _params(
                specific_asset_ids=[
                    {
                        "name": "partInstanceId",
                        "value": "SN-111",
                        "externalSubjectId": {"keys": []},
                    }
                ]
            )
        )
        (encoded,) = params.asset_id_query()
        decoded = json.loads(base64.urlsafe_b64decode(encoded + "==").decode())
        assert "externalSubjectId" in decoded

    def test_a_lookup_with_no_criteria_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            ShellLookupParams.model_validate(_params(specific_asset_ids=[]))


class TestShellLookup:
    @pytest.mark.asyncio
    async def test_returns_the_matching_ids_and_their_descriptors(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(
                _Response(200, {"result": [_SHELL_ID]}), _Response(200, _DESCRIPTOR)
            ),
        ):
            output = await ShellLookupStep().invoke(_params(), context, _definition())

        assert output.value["shell_ids"] == [_SHELL_ID]
        assert output.value["shell_descriptors"] == [_DESCRIPTOR]

    @pytest.mark.asyncio
    async def test_the_lookup_is_addressed_to_the_registry_behind_the_dataplane(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as get:
            await ShellLookupStep().invoke(_params(), context, _definition())

        url, kwargs = get.call_args.args[0], get.call_args.kwargs
        assert url == f"{_DATAPLANE}/lookup/shells"
        assert kwargs["headers"]["Authorization"] == _TOKEN
        assert len(kwargs["params"]["assetIds"]) == 1

    @pytest.mark.asyncio
    async def test_the_dataplane_pair_falls_back_to_what_the_transfer_published(
        self, context: MagicMock
    ) -> None:
        """A script that ran ``initiate_transfer`` first passes neither."""
        context.set_variable(DATAPLANE_URL, _DATAPLANE)
        context.set_variable(EDR_TOKEN, _TOKEN)

        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as get:
            await ShellLookupStep().invoke(
                {"specific_asset_ids": [{"name": "partInstanceId", "value": "SN-111"}]},
                context,
                _definition(),
            )

        assert get.call_args.args[0] == f"{_DATAPLANE}/lookup/shells"
        assert get.call_args.kwargs["headers"]["Authorization"] == _TOKEN

    @pytest.mark.asyncio
    async def test_a_bare_list_answer_is_read_the_same_way(
        self, context: MagicMock
    ) -> None:
        """Registries older than the AAS v3 paging shape answer with the list."""
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, [_SHELL_ID]), _Response(200, _DESCRIPTOR)),
        ):
            output = await ShellLookupStep().invoke(_params(), context, _definition())

        assert output.value["shell_ids"] == [_SHELL_ID]

    @pytest.mark.asyncio
    async def test_a_failed_lookup_is_reported_not_raised(self, context: MagicMock) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(403, None)),
        ):
            output = await ShellLookupStep().invoke(_params(), context, _definition())

        assert output.response.status_code == 403
        assert output.value["shell_ids"] == []

    @pytest.mark.asyncio
    async def test_a_shell_the_registry_will_not_hand_over_leaves_its_id_behind(
        self, context: MagicMock
    ) -> None:
        """The identifier stays readable, so a script can assert on the gap."""
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(
                _Response(200, {"result": [_SHELL_ID]}), _Response(404, None)
            ),
        ):
            output = await ShellLookupStep().invoke(_params(), context, _definition())

        assert output.value["shell_ids"] == [_SHELL_ID]
        assert output.value["shell_descriptors"] == []

    @pytest.mark.asyncio
    async def test_each_descriptor_is_read_by_its_encoded_identifier(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(
                _Response(200, {"result": [_SHELL_ID]}), _Response(200, _DESCRIPTOR)
            ),
        ) as get:
            await ShellLookupStep().invoke(_params(), context, _definition())

        descriptor_url = get.call_args_list[1].args[0]
        encoded = descriptor_url.rsplit("/", 1)[-1]
        assert base64.urlsafe_b64decode(encoded + "==").decode() == _SHELL_ID


# ---------------------------------------------------------------------------
# The same lookup, against the registry the run was seeded with
# ---------------------------------------------------------------------------

_REGISTRY_API = "https://registry.example.com/api/v3.0"
_REGISTRY_LOOKUP = "https://registry-lookup.example.com/api/v3.0"


def _provider_definition() -> StepDefinition:
    return StepDefinition(id="lookup", uses="digital-twin/provider/lookup_shells")


def _provider_params(**overrides: Any) -> dict:
    return {
        "specific_asset_ids": [{"name": "partInstanceId", "value": "SN-111"}],
        **overrides,
    }


@pytest.fixture()
def registry_context(context: MagicMock) -> MagicMock:
    """A context whose seeded AAS service serves its API and lookup separately."""
    aas = MagicMock()
    aas.aas_url = _REGISTRY_API
    aas.aas_lookup_url = _REGISTRY_LOOKUP
    aas._prepare_headers = MagicMock(
        side_effect=lambda bpn=None, method="GET": {
            "Accept": "application/json",
            **({"Edc-Bpn": bpn} if bpn else {}),
        }
    )
    context.get_aas_service = MagicMock(return_value=aas)
    return context


class TestProviderShellLookup:
    @pytest.mark.asyncio
    async def test_returns_the_matching_ids_and_their_descriptors(
        self, registry_context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(
                _Response(200, {"result": [_SHELL_ID]}), _Response(200, _DESCRIPTOR)
            ),
        ):
            output = await ProviderShellLookupStep().invoke(
                _provider_params(), registry_context, _provider_definition()
            )

        # The same answer as the consumer lookup: a setup phase reads it the way
        # an execution phase does.
        assert output.value["shell_ids"] == [_SHELL_ID]
        assert output.value["shell_descriptors"] == [_DESCRIPTOR]

    @pytest.mark.asyncio
    async def test_it_searches_the_seeded_registry_with_no_dataplane_in_between(
        self, registry_context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as get:
            await ProviderShellLookupStep().invoke(
                _provider_params(), registry_context, _provider_definition()
            )

        url, kwargs = get.call_args.args[0], get.call_args.kwargs
        # The service's lookup URL, and no EDR token anywhere: this is the run's
        # own registry, so there is nothing to negotiate first.
        assert url == f"{_REGISTRY_LOOKUP}/lookup/shells"
        assert "Authorization" not in kwargs["headers"]
        assert len(kwargs["params"]["assetIds"]) == 1

    @pytest.mark.asyncio
    async def test_the_criteria_travel_base64url_encoded_as_the_aas_api_asks(
        self, registry_context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as get:
            await ProviderShellLookupStep().invoke(
                _provider_params(), registry_context, _provider_definition()
            )

        (encoded,) = get.call_args.kwargs["params"]["assetIds"]
        decoded = json.loads(base64.urlsafe_b64decode(encoded + "==").decode())
        assert decoded == {"name": "partInstanceId", "value": "SN-111"}

    @pytest.mark.asyncio
    async def test_the_bpn_selects_the_tenant_the_registry_answers_for(
        self, registry_context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as get:
            await ProviderShellLookupStep().invoke(
                _provider_params(bpn="BPNL000000000001"),
                registry_context,
                _provider_definition(),
            )

        assert get.call_args.kwargs["headers"]["Edc-Bpn"] == "BPNL000000000001"

    @pytest.mark.asyncio
    async def test_descriptors_are_read_from_the_registry_api_not_the_lookup_url(
        self, registry_context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(
                _Response(200, {"result": [_SHELL_ID]}), _Response(200, _DESCRIPTOR)
            ),
        ) as get:
            await ProviderShellLookupStep().invoke(
                _provider_params(), registry_context, _provider_definition()
            )

        # A DTR may serve its lookup and its descriptors from different hosts;
        # reading descriptors off the lookup URL would 404 on exactly those.
        descriptor_url = get.call_args_list[1].args[0]
        assert descriptor_url.startswith(f"{_REGISTRY_API}/shell-descriptors/")

    @pytest.mark.asyncio
    async def test_a_failed_lookup_is_reported_not_raised(
        self, registry_context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(404, None)),
        ):
            output = await ProviderShellLookupStep().invoke(
                _provider_params(), registry_context, _provider_definition()
            )

        assert output.value["shell_ids"] == []

    def test_a_lookup_with_no_criteria_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProviderShellLookupParams.model_validate(
                _provider_params(specific_asset_ids=[])
            )


# ---------------------------------------------------------------------------
# The body-carried lookup — POST /lookup/shellsByAssetLink
# ---------------------------------------------------------------------------


def _asset_link_definition() -> StepDefinition:
    return StepDefinition(
        id="lookup_by_link",
        uses="digital-twin-registry/consumer/dataplane/lookup_shells_by_asset_link",
    )


class TestAssetLinkBody:
    def test_the_criteria_travel_as_plain_json_not_base64(self) -> None:
        params = ShellLookupByAssetLinkParams.model_validate(_params())
        assert params.asset_link_body() == [{"name": "partInstanceId", "value": "SN-111"}]

    def test_a_criterion_the_aas_spec_adds_is_kept(self) -> None:
        params = ShellLookupByAssetLinkParams.model_validate(
            _params(
                specific_asset_ids=[
                    {
                        "name": "partInstanceId",
                        "value": "SN-111",
                        "externalSubjectId": {"keys": []},
                    }
                ]
            )
        )
        assert params.asset_link_body()[0]["externalSubjectId"] == {"keys": []}

    def test_paging_parameters_the_script_left_out_are_not_sent(self) -> None:
        assert ShellLookupByAssetLinkParams.model_validate(_params()).page_query() == {}

    def test_paging_parameters_the_script_set_are_sent(self) -> None:
        params = ShellLookupByAssetLinkParams.model_validate(_params(limit=5, cursor="c1"))
        assert params.page_query() == {"limit": 5, "cursor": "c1"}

    def test_a_lookup_with_no_criteria_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            ShellLookupByAssetLinkParams.model_validate(_params(specific_asset_ids=[]))


class TestShellLookupByAssetLink:
    @pytest.mark.asyncio
    async def test_the_lookup_is_posted_to_the_asset_link_endpoint(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.post",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as post:
            await ShellLookupByAssetLinkStep().invoke(
                _params(), context, _asset_link_definition()
            )

        url, kwargs = post.call_args.args[0], post.call_args.kwargs
        assert url == f"{_DATAPLANE}/lookup/shellsByAssetLink"
        assert kwargs["json"] == [{"name": "partInstanceId", "value": "SN-111"}]
        assert kwargs["headers"]["Authorization"] == _TOKEN
        assert kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_returns_the_matching_ids_and_their_descriptors(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.post",
            side_effect=_responses(_Response(200, {"result": [_SHELL_ID]})),
        ), patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, _DESCRIPTOR)),
        ):
            output = await ShellLookupByAssetLinkStep().invoke(
                _params(), context, _asset_link_definition()
            )

        assert output.value["shell_ids"] == [_SHELL_ID]
        assert output.value["shell_descriptors"] == [_DESCRIPTOR]

    @pytest.mark.asyncio
    async def test_the_next_pages_cursor_is_handed_back(self, context: MagicMock) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.post",
            side_effect=_responses(
                _Response(200, {"result": [], "paging_metadata": {"cursor": "next-page"}})
            ),
        ):
            output = await ShellLookupByAssetLinkStep().invoke(
                _params(), context, _asset_link_definition()
            )

        assert output.value["cursor"] == "next-page"

    @pytest.mark.asyncio
    async def test_the_last_page_reports_no_cursor(self, context: MagicMock) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.post",
            side_effect=_responses(_Response(200, {"result": [], "paging_metadata": {}})),
        ):
            output = await ShellLookupByAssetLinkStep().invoke(
                _params(), context, _asset_link_definition()
            )

        assert output.value["cursor"] is None

    @pytest.mark.asyncio
    async def test_a_bare_list_answer_is_read_the_same_way(self, context: MagicMock) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.post",
            side_effect=_responses(_Response(200, [_SHELL_ID])),
        ), patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, _DESCRIPTOR)),
        ):
            output = await ShellLookupByAssetLinkStep().invoke(
                _params(), context, _asset_link_definition()
            )

        assert output.value["shell_ids"] == [_SHELL_ID]
        assert output.value["cursor"] is None

    @pytest.mark.asyncio
    async def test_the_dataplane_pair_falls_back_to_what_the_transfer_published(
        self, context: MagicMock
    ) -> None:
        context.set_variable(DATAPLANE_URL, _DATAPLANE)
        context.set_variable(EDR_TOKEN, _TOKEN)

        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.post",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as post:
            await ShellLookupByAssetLinkStep().invoke(
                {"specific_asset_ids": [{"name": "partInstanceId", "value": "SN-111"}]},
                context,
                _asset_link_definition(),
            )

        assert post.call_args.args[0] == f"{_DATAPLANE}/lookup/shellsByAssetLink"
        assert post.call_args.kwargs["headers"]["Authorization"] == _TOKEN

    @pytest.mark.asyncio
    async def test_a_failed_lookup_is_reported_not_raised(self, context: MagicMock) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.post",
            side_effect=_responses(_Response(403, None)),
        ):
            output = await ShellLookupByAssetLinkStep().invoke(
                _params(), context, _asset_link_definition()
            )

        assert output.response.status_code == 403
        assert output.value["shell_ids"] == []
        assert output.value["cursor"] is None


# ---------------------------------------------------------------------------
# The consumer-side reads of the provider's registry operations
# ---------------------------------------------------------------------------


def _dataplane_params(**overrides: Any) -> dict:
    return {"dataplane_url": _DATAPLANE, "edr_token": _TOKEN, **overrides}


class TestDataplaneGetShellDescriptors:
    @pytest.mark.asyncio
    async def test_lists_the_descriptors_and_their_identifiers(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": [_DESCRIPTOR]})),
        ):
            output = await DataplaneGetShellDescriptorsStep().invoke(
                _dataplane_params(), context, _definition()
            )

        assert output.value["shell_ids"] == [_SHELL_ID]
        assert output.value["shell_descriptors"] == [_DESCRIPTOR]

    @pytest.mark.asyncio
    async def test_the_listing_is_addressed_to_the_registry_behind_the_dataplane(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as get:
            await DataplaneGetShellDescriptorsStep().invoke(
                _dataplane_params(), context, _definition()
            )

        assert get.call_args.args[0] == f"{_DATAPLANE}/shell-descriptors"
        assert get.call_args.kwargs["headers"]["Authorization"] == _TOKEN

    @pytest.mark.asyncio
    async def test_the_dataplane_pair_falls_back_to_what_the_transfer_published(
        self, context: MagicMock
    ) -> None:
        context.set_variable(DATAPLANE_URL, _DATAPLANE)
        context.set_variable(EDR_TOKEN, _TOKEN)

        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, [_DESCRIPTOR])),
        ) as get:
            output = await DataplaneGetShellDescriptorsStep().invoke(
                {}, context, _definition()
            )

        assert get.call_args.args[0] == f"{_DATAPLANE}/shell-descriptors"
        assert output.value["shell_descriptors"] == [_DESCRIPTOR]

    @pytest.mark.asyncio
    async def test_a_failed_listing_is_reported_not_raised(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(403, None)),
        ):
            output = await DataplaneGetShellDescriptorsStep().invoke(
                _dataplane_params(), context, _definition()
            )

        assert output.response.status_code == 403
        assert output.value["shell_descriptors"] == []

    @pytest.mark.asyncio
    async def test_paging_parameters_travel_as_the_query(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, {"result": []})),
        ) as get:
            await DataplaneGetShellDescriptorsStep().invoke(
                _dataplane_params(limit=5, cursor="c1"), context, _definition()
            )

        assert get.call_args.kwargs["params"] == {"limit": 5, "cursor": "c1"}

    @pytest.mark.asyncio
    async def test_the_next_pages_cursor_is_handed_back(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(
                _Response(200, {"result": [], "paging_metadata": {"cursor": "next-page"}})
            ),
        ):
            output = await DataplaneGetShellDescriptorsStep().invoke(
                _dataplane_params(), context, _definition()
            )

        assert output.value["cursor"] == "next-page"


class TestDataplaneGetShellDescriptor:
    @pytest.mark.asyncio
    async def test_reads_the_descriptor_by_its_encoded_identifier(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(200, _DESCRIPTOR)),
        ) as get:
            output = await DataplaneGetShellDescriptorStep().invoke(
                _dataplane_params(aas_identifier=_SHELL_ID), context, _definition()
            )

        encoded = get.call_args.args[0].rsplit("/", 1)[-1]
        assert base64.urlsafe_b64decode(encoded + "==").decode() == _SHELL_ID
        assert get.call_args.kwargs["headers"]["Authorization"] == _TOKEN
        assert output.value["id"] == _SHELL_ID
        assert output.value["id_short"] == "twin-a"

    @pytest.mark.asyncio
    async def test_a_shell_the_registry_will_not_hand_over_keeps_its_status(
        self, context: MagicMock
    ) -> None:
        with patch(
            "tractusx_testlab.steps.industry.dtr.requests.get",
            side_effect=_responses(_Response(404, None)),
        ):
            output = await DataplaneGetShellDescriptorStep().invoke(
                _dataplane_params(aas_identifier=_SHELL_ID), context, _definition()
            )

        assert output.response.status_code == 404
        assert output.value.get("id") is None

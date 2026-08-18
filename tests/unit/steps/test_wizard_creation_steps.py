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

"""Contract tests for the guided creation steps (C26).

Each wizard step is the flat-field sibling of a step that takes the whole
document.  What these tests hold to is that the pair stays a pair: the wizard
assembles a document and then registers it through the same call, so the two
cannot drift apart in what they actually create.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import attach_endpoint_url_stubs
from tractusx_testlab.models import StepDefinition
from tractusx_testlab.steps.connector.provision.asset import (
    CreateAssetStep,
    WizardCreateAssetParams,
    WizardCreateAssetStep,
)
from tractusx_testlab.steps.connector.provision.policy import (
    CreatePolicyStep,
    WizardCreatePolicyParams,
    WizardCreatePolicyStep,
)
from tractusx_testlab.steps.digital_twin.provider.shell import (
    CreateShellDescriptorStep,
    WizardCreateShellDescriptorParams,
    WizardCreateShellDescriptorStep,
)
from tractusx_testlab.steps.digital_twin.provider.submodel_descriptor import (
    WizardCreateSubmodelDescriptorParams,
    WizardCreateSubmodelDescriptorStep,
)


def _definition(uses: str) -> StepDefinition:
    return StepDefinition(id="s", uses=uses)


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


@pytest.fixture()
def provider() -> MagicMock:
    service = MagicMock()
    service.dataspace_version = "jupiter"
    service.create_asset.return_value = {"@id": "asset-1"}
    service.create_policy.return_value = {"@id": "policy-1"}
    return service


@pytest.fixture()
def connector_context(provider: MagicMock) -> MagicMock:
    ctx = attach_endpoint_url_stubs(MagicMock())
    ctx.dataspace.provider_base_url.return_value = "https://provider.example.com"
    ctx.dataspace.provider.return_value = provider
    return ctx


class TestWizardCreateAsset:
    def test_the_guided_fields_become_edc_asset_properties(self) -> None:
        params = WizardCreateAssetParams(
            name="CCM API",
            description="Certificate management",
            base_url="https://backend.example.com",
            content_type="application/json",
            properties={"dct:type": {"@id": "https://w3id.org/catenax/taxonomy#CCMAPI"}},
        )
        properties = params.asset_config()["properties"]
        assert properties["name"] == "CCM API"
        assert properties["description"] == "Certificate management"
        assert properties["contenttype"] == "application/json"
        assert properties["dct:type"] == {"@id": "https://w3id.org/catenax/taxonomy#CCMAPI"}

    def test_an_explicit_property_is_not_overwritten(self) -> None:
        params = WizardCreateAssetParams(
            name="CCM API", base_url="https://b", properties={"name": "kept"}
        )
        assert params.asset_config()["properties"]["name"] == "kept"

    @pytest.mark.asyncio
    async def test_it_registers_through_the_same_call_as_the_raw_step(
        self, connector_context: MagicMock, provider: MagicMock
    ) -> None:
        await WizardCreateAssetStep().invoke(
            {"name": "CCM API", "base_url": "https://backend.example.com"},
            connector_context,
            _definition("connector/provider/wizard/create_asset"),
        )
        wizard_call = provider.create_asset.call_args.kwargs

        provider.create_asset.reset_mock()
        await CreateAssetStep().invoke(
            {"asset": {"name": "CCM API", "base_url": "https://backend.example.com"}},
            connector_context,
            _definition("connector/provider/create_asset"),
        )

        assert wizard_call == provider.create_asset.call_args.kwargs

    @pytest.mark.asyncio
    async def test_an_omitted_id_is_derived_from_the_name(
        self, connector_context: MagicMock
    ) -> None:
        output = await WizardCreateAssetStep().invoke(
            {"name": "CCM API", "base_url": "https://backend.example.com"},
            connector_context,
            _definition("connector/provider/wizard/create_asset"),
        )
        assert output.value["asset_id"] == "ccm-api"


class TestWizardCreatePolicy:
    def test_the_rule_lists_become_one_odrl_document(self) -> None:
        params = WizardCreatePolicyParams(
            permissions=[{"action": "use"}], prohibitions=[{"action": "modify"}]
        )
        assert params.policy_document() == {
            "permissions": [{"action": "use"}],
            "prohibitions": [{"action": "modify"}],
            "obligations": [],
        }

    @pytest.mark.asyncio
    async def test_it_registers_through_the_same_call_as_the_raw_step(
        self, connector_context: MagicMock, provider: MagicMock
    ) -> None:
        await WizardCreatePolicyStep().invoke(
            {"policy_id": "p-1", "permissions": [{"action": "use"}]},
            connector_context,
            _definition("connector/provider/wizard/create_policy"),
        )
        wizard_call = provider.create_policy.call_args.kwargs

        provider.create_policy.reset_mock()
        await CreatePolicyStep().invoke(
            {"policy": {"policy_id": "p-1", "permissions": [{"action": "use"}]}},
            connector_context,
            _definition("connector/provider/create_policy"),
        )

        assert wizard_call == provider.create_policy.call_args.kwargs

    @pytest.mark.asyncio
    async def test_a_policy_with_no_permissions_is_rejected(
        self, connector_context: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="permissions"):
            await WizardCreatePolicyStep().invoke(
                {}, connector_context, _definition("connector/provider/wizard/create_policy")
            )


# ---------------------------------------------------------------------------
# Digital Twin Registry
# ---------------------------------------------------------------------------


@pytest.fixture()
def aas() -> MagicMock:
    service = MagicMock()
    service.aas_url = "https://dtr.example.com/api/v3"
    service.create_asset_administration_shell_descriptor.return_value = {"id": "shell-1"}
    service.create_submodel_descriptor.return_value = {"id": "submodel-1"}
    return service


@pytest.fixture()
def dtr_context(aas: MagicMock) -> MagicMock:
    ctx = attach_endpoint_url_stubs(MagicMock())
    ctx.dataspace.registry.return_value = aas
    return ctx


def _shell_sent(aas: MagicMock) -> Any:
    return aas.create_asset_administration_shell_descriptor.call_args.args[0]


class TestWizardCreateShellDescriptor:
    def test_an_omitted_id_becomes_a_urn_uuid(self) -> None:
        params = WizardCreateShellDescriptorParams(id_short="twin-a")
        assert params.shell_document()["id"].startswith("urn:uuid:")

    def test_optional_fields_absent_are_not_invented(self) -> None:
        """An empty ``specificAssetIds`` is a claim; leaving it out is not."""
        document = WizardCreateShellDescriptorParams(id_short="twin-a").shell_document()
        assert set(document) == {"id", "idShort"}

    def test_the_guided_fields_become_the_aas_spellings(self) -> None:
        document = WizardCreateShellDescriptorParams(
            id="urn:uuid:1",
            id_short="twin-a",
            global_asset_id="urn:uuid:2",
            specific_asset_ids=[{"name": "partInstanceId", "value": "SN-1"}],
        ).shell_document()
        assert document["idShort"] == "twin-a"
        assert document["globalAssetId"] == "urn:uuid:2"
        assert document["specificAssetIds"] == [{"name": "partInstanceId", "value": "SN-1"}]

    @pytest.mark.asyncio
    async def test_it_registers_through_the_same_call_as_the_raw_step(
        self, dtr_context: MagicMock, aas: MagicMock
    ) -> None:
        document = {"id": "urn:uuid:1", "idShort": "twin-a"}

        await WizardCreateShellDescriptorStep().invoke(
            {"id": "urn:uuid:1", "id_short": "twin-a"},
            dtr_context,
            _definition("digital-twin/provider/wizard/create_shell_descriptor"),
        )
        from_wizard = _shell_sent(aas)

        await CreateShellDescriptorStep().invoke(
            {"shell_descriptor": document},
            dtr_context,
            _definition("digital-twin/provider/create_shell_descriptor"),
        )

        assert from_wizard == _shell_sent(aas)


class TestWizardCreateSubmodelDescriptor:
    def test_the_semantic_id_becomes_an_external_reference(self) -> None:
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            id_short="serialPart",
            semantic_id="urn:samm:io.catenax.serial_part:3.0.0#SerialPart",
            href="https://dataplane.example.com/submodel",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
        ).submodel_document()
        assert document["semanticId"]["keys"] == [
            {
                "type": "GlobalReference",
                "value": "urn:samm:io.catenax.serial_part:3.0.0#SerialPart",
            }
        ]

    def test_the_href_becomes_the_submodel_endpoint(self) -> None:
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            id_short="serialPart",
            semantic_id="urn:samm:x#Y",
            href="https://dataplane.example.com/submodel",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
        ).submodel_document()
        (endpoint,) = document["endpoints"]
        assert endpoint["interface"] == "SUBMODEL-3.0"
        assert endpoint["protocolInformation"]["href"] == (
            "https://dataplane.example.com/submodel"
        )

    def test_the_asset_and_control_plane_become_the_subprotocol_body(self) -> None:
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            id_short="serialPart",
            semantic_id="urn:samm:x#Y",
            href="https://dataplane.example.com/submodel",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
        ).submodel_document()
        (endpoint,) = document["endpoints"]
        protocol = endpoint["protocolInformation"]
        assert protocol["subprotocol"] == "DSP"
        assert protocol["subprotocolBodyEncoding"] == "plain"
        assert protocol["subprotocolBody"] == (
            "id=urn:uuid:asset;dspEndpoint=https://provider.example.com/api/v1/dsp"
        )

    def test_the_keys_the_standard_fixes_are_written_not_asked_for(self) -> None:
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            semantic_id="urn:samm:x#Y",
            href="https://dataplane.example.com/submodel",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
        ).submodel_document()
        protocol = document["endpoints"][0]["protocolInformation"]
        assert protocol["endpointProtocol"] == "HTTP"
        assert protocol["endpointProtocolVersion"] == ["1.1"]
        assert protocol["subprotocol"] == "DSP"
        assert protocol["subprotocolBodyEncoding"] == "plain"

    def test_an_omitted_id_short_is_left_out_of_the_descriptor(self) -> None:
        """CX-0002 asks for no idShort, and an empty one is not a name."""
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            semantic_id="urn:samm:x#Y",
            href="https://dataplane.example.com/submodel",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
        ).submodel_document()
        assert "idShort" not in document

    def test_a_value_interface_appends_the_value_suffix(self) -> None:
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            id_short="serialPart",
            semantic_id="urn:samm:x#Y",
            href="https://dataplane.example.com/api/public",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
            interface="SUBMODEL-VALUE-3.2",
        ).submodel_document()
        (endpoint,) = document["endpoints"]
        assert endpoint["protocolInformation"]["href"] == (
            "https://dataplane.example.com/api/public/submodel/$value"
        )

    def test_a_value_interface_completes_a_submodel_href(self) -> None:
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            id_short="serialPart",
            semantic_id="urn:samm:x#Y",
            href="https://dataplane.example.com/submodel",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
            interface="SUBMODEL-VALUE-3.1",
        ).submodel_document()
        (endpoint,) = document["endpoints"]
        assert endpoint["protocolInformation"]["href"] == (
            "https://dataplane.example.com/submodel/$value"
        )

    def test_the_submodel_interface_drops_a_pasted_value_suffix(self) -> None:
        document = WizardCreateSubmodelDescriptorParams(
            aas_identifier="urn:uuid:1",
            id_short="serialPart",
            semantic_id="urn:samm:x#Y",
            href="https://dataplane.example.com/submodel/$value",
            asset_id="urn:uuid:asset",
            dsp_endpoint="https://provider.example.com/api/v1/dsp",
        ).submodel_document()
        (endpoint,) = document["endpoints"]
        assert endpoint["protocolInformation"]["href"] == (
            "https://dataplane.example.com/submodel"
        )

    @pytest.mark.asyncio
    async def test_the_suffix_is_on_the_href_the_registry_is_actually_sent(
        self, dtr_context: MagicMock, aas: MagicMock
    ) -> None:
        """The concatenation has to survive the whole step, not just the model.

        ``submodel_document`` is where the suffix is written, but the descriptor
        that reaches the registry is the one the step hands to
        ``create_submodel_descriptor`` — so this reads the href back off the
        request the step reports having made.
        """
        output = await WizardCreateSubmodelDescriptorStep().invoke(
            {
                "aas_identifier": "urn:uuid:shell",
                "semantic_id": "urn:samm:x#Y",
                "href": "https://dataplane.example.com/api/public",
                "asset_id": "urn:uuid:asset",
                "dsp_endpoint": "https://provider.example.com/api/v1/dsp",
                "interface": "SUBMODEL-VALUE-3.2",
            },
            dtr_context,
            _definition("digital-twin/provider/wizard/create_submodel_descriptor"),
        )

        sent = output.request.body
        assert sent["endpoints"][0]["protocolInformation"]["href"] == (
            "https://dataplane.example.com/api/public/submodel/$value"
        )
        assert aas.create_submodel_descriptor.call_args.args[0] == "urn:uuid:shell"

    @pytest.mark.asyncio
    async def test_the_registry_is_sent_the_bare_href_for_a_plain_interface(
        self, dtr_context: MagicMock
    ) -> None:
        output = await WizardCreateSubmodelDescriptorStep().invoke(
            {
                "aas_identifier": "urn:uuid:shell",
                "semantic_id": "urn:samm:x#Y",
                "href": "https://dataplane.example.com/api/public",
                "asset_id": "urn:uuid:asset",
                "dsp_endpoint": "https://provider.example.com/api/v1/dsp",
            },
            dtr_context,
            _definition("digital-twin/provider/wizard/create_submodel_descriptor"),
        )

        sent = output.request.body
        assert sent["endpoints"][0]["protocolInformation"]["href"] == (
            "https://dataplane.example.com/api/public"
        )

    @pytest.mark.asyncio
    async def test_it_is_attached_to_the_shell_it_names(
        self, dtr_context: MagicMock, aas: MagicMock
    ) -> None:
        await WizardCreateSubmodelDescriptorStep().invoke(
            {
                "aas_identifier": "urn:uuid:shell",
                "id_short": "serialPart",
                "semantic_id": "urn:samm:x#Y",
                "href": "https://dataplane.example.com/submodel",
                "asset_id": "urn:uuid:asset",
                "dsp_endpoint": "https://provider.example.com/api/v1/dsp",
            },
            dtr_context,
            _definition("digital-twin/provider/wizard/create_submodel_descriptor"),
        )
        assert aas.create_submodel_descriptor.call_args.args[0] == "urn:uuid:shell"

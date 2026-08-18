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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.


"""Shell descriptors at a registry the engine operates.

Registering a shell, reading one back, looking shells up by their
``specificAssetIds``, and removing one — the descriptor's own lifecycle. The
submodel descriptors that hang off a shell are next door in
:mod:`~tractusx_testlab.steps.digital_twin.provider.submodel_descriptor`.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import Field

from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps import http_client, sdk_call
from tractusx_testlab.steps.registry_models import (
    DescriptorPayload,
    DtrParams,
    ShellLookupOutput,
    SpecificAssetId,
    _as_document,
    _asset_ids_query,
)
from tractusx_testlab.steps.registry_reading import (
    _shell_descriptor,
    _shell_ids,
)
from tractusx_testlab.steps.shared_models import (
    DeletionOutput,
)
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------


class CreateShellDescriptorParams(DtrParams):
    """Input contract of ``digital-twin/provider/create_shell_descriptor``."""

    shell_descriptor: dict = Field(
        description="The AAS shell descriptor document to register."
    )


@step("digital-twin/provider/create_shell_descriptor")
class CreateShellDescriptorStep(BaseStep[CreateShellDescriptorParams, DescriptorPayload]):
    """Create an AAS shell descriptor in the Digital Twin Registry."""

    params_model = CreateShellDescriptorParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: CreateShellDescriptorParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        return await _register_shell(context, params.shell_descriptor, params.bpn)


async def _register_shell(
    context: StepContext, shell_descriptor: dict, bpn: str | None
) -> StepOutput[DescriptorPayload]:
    """Register a shell descriptor, whether it was written out or assembled.

    The one place either shell-creation step reaches the registry, so the two
    cannot drift apart in what they register.
    """
    from tractusx_sdk.industry.models.aas.v3.base import ShellDescriptor

    aas = context.dataspace.registry()
    result = await sdk_call.run(aas.create_asset_administration_shell_descriptor,
        ShellDescriptor(**shell_descriptor), bpn=bpn
    )
    url = f"{aas.aas_url}/shell-descriptors"

    body = _as_document(result)
    return StepOutput(
        value=DescriptorPayload.of(body),
        request=HttpRequest(method="POST", url=url, body=shell_descriptor),
        response=HttpResponse(status_code=201, body=body),
    )


# ---------------------------------------------------------------------------
# digital-twin/provider/wizard/create_shell_descriptor
# ---------------------------------------------------------------------------


class WizardCreateShellDescriptorParams(DtrParams):
    """Input contract of ``digital-twin/provider/wizard/create_shell_descriptor``.

    The same shell as ``digital-twin/provider/create_shell_descriptor``
    registers, described field by field instead of as one AAS document.
    """

    id: str = Field(
        default="", description="Shell identifier; a fresh URN UUID when omitted."
    )
    id_short: str = Field(description="Short, human-readable name for the shell.")
    global_asset_id: str = Field(
        default="", description="Global asset ID the twin represents, as a URN."
    )
    specific_asset_ids: list[dict] = Field(
        default_factory=list,
        description="Identifiers the shell can be looked up by, as {name, value} pairs.",
    )
    submodel_descriptors: list[dict] = Field(
        default_factory=list,
        description="Submodel descriptors to attach as the shell is created.",
    )

    def shell_document(self) -> dict:
        """The AAS shell descriptor these fields describe."""
        document: dict[str, Any] = {
            "id": self.id or f"urn:uuid:{uuid.uuid4()}",
            "idShort": self.id_short,
        }
        if self.global_asset_id:
            document["globalAssetId"] = self.global_asset_id
        if self.specific_asset_ids:
            document["specificAssetIds"] = self.specific_asset_ids
        if self.submodel_descriptors:
            document["submodelDescriptors"] = self.submodel_descriptors
        return document


@step("digital-twin/provider/wizard/create_shell_descriptor")
class WizardCreateShellDescriptorStep(
    BaseStep[WizardCreateShellDescriptorParams, DescriptorPayload]
):
    """Register a shell descriptor described field by field.

    The guided sibling of ``digital-twin/provider/create_shell_descriptor``,
    registering through the same call.
    """

    params_model = WizardCreateShellDescriptorParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: WizardCreateShellDescriptorParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        return await _register_shell(context, params.shell_document(), params.bpn)


# ---------------------------------------------------------------------------
# digital-twin/provider/get_shell_descriptor
# ---------------------------------------------------------------------------


class ShellDescriptorRefParams(DtrParams):
    """Names an existing shell descriptor."""

    aas_identifier: str = Field(description="Identifier of the AAS shell descriptor.")


@step("digital-twin/provider/get_shell_descriptor")
class GetShellDescriptorStep(BaseStep[ShellDescriptorRefParams, DescriptorPayload]):
    """Retrieve an AAS shell descriptor by ID."""

    params_model = ShellDescriptorRefParams
    output_model = DescriptorPayload

    async def execute(
        self,
        params: ShellDescriptorRefParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DescriptorPayload]:
        aas = context.dataspace.registry()
        result = await sdk_call.run(aas.get_asset_administration_shell_descriptor_by_id,
            params.aas_identifier, bpn=params.bpn
        )
        url = f"{aas.aas_url}/shell-descriptors/{params.aas_identifier}"

        body = _as_document(result)
        return StepOutput(
            value=DescriptorPayload.of(body),
            request=HttpRequest(method="GET", url=url),
            response=HttpResponse(status_code=200, body=body),
        )


# ---------------------------------------------------------------------------
# digital-twin/provider/lookup_shells
# ---------------------------------------------------------------------------


class ProviderShellLookupParams(DtrParams):
    """Input contract of ``digital-twin/provider/lookup_shells``.

    Only the criteria: the registry is the one the run was seeded with, so its
    address is the service's, not the script's — which is the whole difference
    from the consumer lookup, where the address is a data plane a transfer
    produced.
    """

    specific_asset_ids: list[SpecificAssetId] = Field(
        min_length=1,
        description="Criteria the shell must match; all of them have to.",
    )


@step("digital-twin/provider/lookup_shells")
class ProviderShellLookupStep(BaseStep[ProviderShellLookupParams, ShellLookupOutput]):
    """Search the run's own registry for shells matching specific asset IDs.

    ``digital-twin-registry/consumer/dataplane/lookup_shell`` re-addressed at the
    registry the engine is seeded with: the same ``GET /lookup/shells``, the same
    base64url-encoded criteria, the same answer, reached over the service's own
    lookup URL rather than through a data plane. That is what a setup phase
    needs — it has no EDR token, and no reason to obtain one to search a
    registry it operates.

    The lookup answers with identifiers, so each is read back as a descriptor
    from the registry API; a script that only needs the identifiers reads
    ``shell_ids`` and ignores the rest.
    """

    params_model = ProviderShellLookupParams
    output_model = ShellLookupOutput

    async def execute(
        self,
        params: ProviderShellLookupParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[ShellLookupOutput]:
        aas = context.dataspace.registry()
        # The SDK assembles the registry's headers — the access token its auth
        # service holds, plus the Edc-Bpn tenant selector. Rebuilding them here
        # would be a second copy of the SDK's auth, free to drift from it, for
        # the one call it does not wrap.
        headers = aas._prepare_headers(params.bpn)
        timeout = context.config.default_timeout_s

        url = f"{aas.aas_lookup_url}/lookup/shells"
        query = {"assetIds": _asset_ids_query(params.specific_asset_ids)}
        response = await http_client.request(
            "GET", url, params=query, headers=headers, timeout=timeout
        )

        shell_ids = _shell_ids(response)
        # Descriptors come from the registry API, not the lookup URL: a DTR may
        # serve the two from different hosts, and the service knows both.
        descriptors = [
            document
            for shell_id in shell_ids
            if (document := await _shell_descriptor(aas.aas_url, shell_id, headers, timeout))
            is not None
        ]

        return StepOutput(
            value=ShellLookupOutput(shell_ids=shell_ids, shell_descriptors=descriptors),
            request=HttpRequest(method="GET", url=url, headers=headers, body=query),
            response=HttpResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body={"shell_ids": shell_ids, "shell_descriptors": descriptors},
            ),
        )


# ---------------------------------------------------------------------------
# digital-twin/provider/delete_shell_descriptor
# ---------------------------------------------------------------------------


#: Status a registry answers a delete it accepted with.  The SDK collapses that
#: answer to ``None``, so the code is written here rather than read back.
_DELETED = 204

#: Status reported when the registry refused the delete but named no code of its
#: own.  400 says the delete did not happen without inventing a reason.
_DELETE_REFUSED = 400


def _delete_status(result: Any) -> int:
    """The status a registry answered a delete with, as far as the SDK reports it.

    ``delete_asset_administration_shell_descriptor`` returns ``None`` when the
    registry accepted the delete and an AAS ``Result`` when it refused, so the
    code of a refusal has to be read out of the refusal document: AAS carries it
    in each message's ``code``.  A registry that puts something else there, or
    sends no message at all, reads as a plain refusal.
    """
    if result is None:
        return _DELETED
    for message in getattr(result, "messages", None) or []:
        code = str(getattr(message, "code", "") or "")
        if code.isdigit():
            return int(code)
    return _DELETE_REFUSED


@step("digital-twin/provider/delete_shell_descriptor")
class DeleteShellDescriptorStep(BaseStep[ShellDescriptorRefParams, DeletionOutput]):
    """Delete an AAS shell descriptor.

    The status the registry answered with is published as ``status_code``, so a
    teardown can assert that the twin was really there (204) rather than already
    gone (404).
    """

    params_model = ShellDescriptorRefParams
    output_model = DeletionOutput

    async def execute(
        self,
        params: ShellDescriptorRefParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DeletionOutput]:
        aas = context.dataspace.registry()
        result = await sdk_call.run(aas.delete_asset_administration_shell_descriptor,
            params.aas_identifier, bpn=params.bpn
        )
        url = f"{aas.aas_url}/shell-descriptors/{params.aas_identifier}"
        status = _delete_status(result)

        return StepOutput(
            value=DeletionOutput(status_code=status),
            request=HttpRequest(method="DELETE", url=url),
            response=HttpResponse(status_code=status, body=result),
        )

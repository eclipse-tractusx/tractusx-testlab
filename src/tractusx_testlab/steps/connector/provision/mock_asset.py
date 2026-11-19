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

"""Offering one of the run's own mocks — ``connector/provider/create_mock_asset``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field, field_validator
from tractusx_sdk.dataspace.models.connector.model_factory import ModelFactory

from tractusx_testlab.authoring.registry import step
from tractusx_testlab.models import HttpRequest, HttpResponse, StepDefinition
from tractusx_testlab.models.primitives.exceptions import AuthoringError, BoundServiceError
from tractusx_testlab.player.execution.dataspace_access import DataspaceAccess
from tractusx_testlab.server.mock_registry import required_header
from tractusx_testlab.steps.connector.provision._shared import _ALREADY_EXISTS, _config_object
from tractusx_testlab.steps.connector.provision.asset import (
    _DEFAULT_ASSET_CONTEXT,
    CreateAssetOutput,
    CreateAssetParams,
    _register_asset,
)
from tractusx_testlab.steps.mock._models import MockInstance
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

#: How the data plane forwards to a mock: the path, the method and the body the
#: system under test sent, and not the query. The SDK's own default turns the
#: body off, and a notification pushed through the data plane is a POST.
_MOCK_PROXY_PARAMS: dict[str, str] = {
    "proxyQueryParams": "false",
    "proxyPath": "true",
    "proxyMethod": "true",
    "proxyBody": "true",
}

#: What the mock supplies, and so what a mock asset config may not.
_SUPPLIED_BY_THE_MOCK = ("base_url", "headers")


class CreateMockAssetParams(StepParams):
    """Input contract of ``connector/provider/create_mock_asset``.

    The asset is described once, statically, by a ``config/connector/mock_asset``
    variable: its id, ``dct_type``, ``dct_subject``, ``version`` and the rest
    of what ``config/connector/asset`` takes. What only exists once the run is
    going — the mock's address and the key it requires — comes from ``mock``.
    """

    asset: dict = Field(
        description=(
            "The asset, as declared by a 'config/connector/mock_asset' variable and "
            "referenced as '${{ env.<id> }}'. Carries 'asset_id', 'dct_type' or "
            "'properties', 'dct_subject', 'version', 'semantic_id', 'proxy_params', "
            "'private_properties' and an optional '@context' — not 'base_url' or "
            "'headers', which the mock supplies."
        ),
    )
    mock: MockInstance = Field(
        description=(
            "The mock the asset fronts, as 'mock/api' returned it. Its root becomes "
            "the data address, and the key it requires a header the data plane sends."
        ),
    )

    base_url: str = Field(
        default="",
        description=(
            "Where the connector's data plane reaches the mock server, when that is not "
            "the root the mock published (the engine's mock_public_url) — a data plane "
            "in another network. Defaults to the mock's 'base_mock_url'."
        ),
    )

    @field_validator("asset", mode="before")
    @classmethod
    def _unwrap_asset(cls, value: Any) -> Any:
        return _config_object(value, "asset")

    @field_validator("asset")
    @classmethod
    def _nothing_the_mock_supplies(cls, value: dict) -> dict:
        given = [key for key in _SUPPLIED_BY_THE_MOCK if key in value]
        if given:
            raise ValueError(
                f"a mock asset takes {' and '.join(given)} from its mock; remove it from the config"
            )
        return value


@step("connector/provider/create_mock_asset")
class CreateMockAssetStep(BaseStep[CreateMockAssetParams, CreateAssetOutput]):
    """Offer one of the run's own mocks as an asset on the engine connector.

    The reflexive asset: the system under test negotiates it and calls through
    its data plane, and the data plane forwards to the engine's mock. The data
    address is the mock server's root, with the path, method and body proxied,
    and carries the key the mock requires as ``header:<name>`` — so a call the
    data plane forwards is answered, and a call made to the mock URL directly
    is refused. The key never appears in the test: it is read from the mock.
    It sits only in the asset's private data address, which neither the
    catalog nor the EDR the system under test receives carries, and it is
    masked wherever the run is written down.

    The key is new every run, so an asset left by an earlier run with the same
    id would forward the wrong one. The connector keeps an existing asset on
    409, so for an asset that is not provably this run's own that is an error
    here rather than the "already there" that ``create_asset`` reports; give
    the asset id the run id (``${{ execution.id }}``) and withdraw it in
    teardown.

    A 409 on this run's own asset — its id carries the run's resource prefix,
    which names the run — is a test run again in the same run (a step-by-step
    session re-running an ``async`` test). The earlier attempt's asset is still
    there: teardown cannot delete it once a contract agreement references it,
    and agreements keep their history even when retired. Its data address is
    then replaced in place (``PUT /v3/assets``) with the one built now, and the
    step passes with the same asset id. Should the connector refuse that
    update, the step fails saying so.
    """

    params_model = CreateMockAssetParams
    output_model = CreateAssetOutput

    async def execute(
        self, params: CreateMockAssetParams, context: StepContext, definition: StepDefinition
    ) -> StepOutput[CreateAssetOutput]:
        mock = params.mock
        guard = required_header(mock.path, mock.method)
        if guard is None:
            raise AuthoringError(
                f"The mock {mock.method} {mock.path} requires no key, so an asset in front "
                "of it would not keep anyone from calling it directly. Register it with "
                "mock/api (not public) in this run before offering it."
            )
        header, key = guard
        base_url = params.base_url or mock.base_mock_url

        config = {
            **params.asset,
            "base_url": base_url,
            "headers": {header: key},
            "proxy_params": params.asset.get("proxy_params") or dict(_MOCK_PROXY_PARAMS),
        }
        assembled = CreateAssetParams(asset=config)
        asset_id = str(params.asset.get("asset_id") or f"testlab-mock-{context.job.job_id}")
        asset_definition = assembled.definition()

        # On the engine's connector whatever else is bound: the mock is the
        # engine's, so an offer of it anywhere else would forward nowhere.
        provider = context.dataspace.engine_provider()
        output = _register_asset(
            context,
            asset_id,
            asset_definition,
            {
                "asset": params.asset,
                "mock": mock.model_dump(mode="json"),
                "data_address": {
                    "baseUrl": base_url,
                    f"header:{header}": key,
                    **asset_definition["proxy_params"],
                },
            },
            provider=provider,
            url=DataspaceAccess._controller_url(
                provider,
                str(context.infrastructure.engine.connector.management_url or ""),
                "assets",
            ),
        )
        if output.response is not None and output.response.status_code == _ALREADY_EXISTS:
            scoped_id = output.value.asset_id
            if _owned_by_this_run(context, scoped_id):
                return _update_asset(
                    provider,
                    scoped_id,
                    asset_definition,
                    request=output.request,
                )
            raise AuthoringError(
                f"Asset '{asset_id}' already exists on the engine connector, and the "
                "connector keeps it as it was — with an earlier run's key, which the "
                "mock refuses. Give the asset id the run id (${{ execution.id }}) and "
                "withdraw it in teardown."
            )
        return output


def _owned_by_this_run(context: StepContext, asset_id: str) -> bool:
    """Whether *asset_id* lies in this run's own resource namespace.

    The namespace is the run's resource prefix, which the player builds from
    the execution id; an id under it can only have been created by this run.
    No prefix, a prefix that does not name the run, or an id outside it, and
    the asset may be another run's — the stale-key case.
    """
    prefix = context.resource_prefix
    run_id = str(context.job.job_id or "")
    return bool(prefix and run_id) and run_id in prefix and asset_id.startswith(prefix)


def _update_asset(
    provider: Any,
    asset_id: str,
    definition: dict[str, Any],
    *,
    request: HttpRequest | None,
) -> StepOutput[CreateAssetOutput]:
    """Replace this run's existing asset with *definition* (``PUT /v3/assets``).

    The SDK's provider has a create shortcut but no update one, so the asset
    is assembled here the way ``create_asset`` assembles it — an ``HttpData``
    address carrying the proxy flags and the key as ``header:<name>`` — and
    sent through the asset controller's ``update``.
    """
    data_address: dict[str, Any] = {
        "@type": "DataAddress",
        "type": "HttpData",
        "baseUrl": definition["base_url"],
        **(definition.get("proxy_params") or {}),
    }
    for name, value in (definition.get("headers") or {}).items():
        data_address[f"header:{name}"] = value
    asset = ModelFactory.get_asset_model(
        dataspace_version=provider.dataspace_version,
        oid=asset_id,
        context=definition.get("context") or dict(_DEFAULT_ASSET_CONTEXT),
        properties=provider.build_properties(
            dct_type=definition.get("dct_type"),
            dct_subject=definition.get("dct_subject"),
            version=definition.get("version"),
            properties=definition.get("properties"),
        ),
        private_properties=definition.get("private_properties"),
        data_address=data_address,
    )

    failure = (
        f"Asset '{asset_id}' is this run's own, left on the engine connector by an earlier "
        "attempt of the test, and the connector would not update it with this attempt's "
        "mock key"
    )
    try:
        response = provider.assets.update(obj=asset, verify=provider.verify_ssl)
    except (OSError, RuntimeError, ValueError) as exc:
        raise BoundServiceError(f"{failure}: {exc}") from exc
    status = getattr(response, "status_code", None)
    if not isinstance(status, int) or not 200 <= status < 300:
        detail = str(getattr(response, "text", "") or "").strip()
        raise BoundServiceError(
            f"{failure}: it answered {status} to PUT /v3/assets"
            + (f" — {detail}" if detail else "")
        )

    return StepOutput(
        value=CreateAssetOutput(asset_id=asset_id),
        request=HttpRequest(
            method="PUT",
            url=request.url if request is not None else "",
            body=request.body if request is not None else None,
        ),
        response=HttpResponse(status_code=status, body={"asset_id": asset_id, "updated": True}),
    )

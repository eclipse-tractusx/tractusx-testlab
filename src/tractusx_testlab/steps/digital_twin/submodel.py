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

"""Submodel-server steps: uploading data under a path, and deleting it again."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx
from pydantic import Field, field_validator

from tractusx_testlab.models import (
    HttpRequest,
    HttpResponse,
    StepConfigError,
    StepDefinition,
)
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.steps.shared_models import DeletionOutput, HttpTransportParams
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput, StepPayload

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

import uuid


def _relative_path(value: Any) -> str | None:
    """Normalize a path under the submodel server, refusing one with a server of its own.

    The server is the engine's (``engine.dtr.submodel_base_url``) — a path allowed to
    carry a scheme and host would be the ``url`` input these steps deliberately
    do not have, and would send a provider's data somewhere the engine never
    agreed to. Surrounding slashes are the caller's punctuation, not part of the
    path, so ``/data/`` and ``data`` land in the same place.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("'path' must be a string")

    candidate = value.strip()
    if "://" in candidate or candidate.startswith("//"):
        raise ValueError(
            "'path' is relative to the engine's submodel server; "
            f"it cannot be an absolute URL: {candidate!r}"
        )

    trimmed = candidate.strip("/")
    return trimmed or None


def _submodel_server(context: StepContext, definition: StepDefinition) -> str:
    """The submodel server the engine was bound to, without its trailing slash.

    An engine without one cannot run these steps, and says so rather than
    addressing a server the script would have had to name itself.
    """
    backend_base_url = (context.infrastructure.engine.dtr.submodel_base_url or "").strip()
    if not backend_base_url:
        raise StepConfigError(
            definition.uses,
            "no submodel server is bound; set engine.dtr.submodel_base_url "
            "(TESTLAB_ENGINE_DTR_SUBMODEL_BASE_URL) on the engine",
        )
    return backend_base_url.rstrip("/")


def _storage_path(semantic_id: str | None, submodel_id: str) -> str:
    """The path a submodel service stores one submodel under.

    The layout is the Industry Core one: a submodel is addressed by the aspect
    it follows and then by its own id, so submodels of the same aspect sit
    together and a data plane can be pointed at the aspect alone. A URN carries
    ``:`` and ``#``, and a raw ``#`` in a URL would start a fragment and cut the
    rest of the address off, so the aspect segment is percent-encoded — the
    same ``quote(..., safe="")`` the hub's submodel adapter uses.

    The id is written as it is, because it is what the TCK stores its data
    under (``.../urn:uuid:<uuid4>``) and ``:`` is legal in a path segment;
    encoding it would name a different resource than every existing test does.

    Without an aspect there is nothing to group by, so the submodel is stored
    directly under the server as ``<server>/<submodel_id>``.
    """
    if not semantic_id:
        return submodel_id
    return f"{quote(semantic_id, safe='')}/{submodel_id}"


class UploadBackendDataParams(HttpTransportParams):
    """Input contract of ``digital-twin/submodel/upload``.

    Only the transport half of an HTTP call: the step always POSTs, so a
    ``method`` input would be a knob that does nothing, and the submodel server
    is the one the engine is bound to (``engine.dtr.submodel_base_url``) rather than
    one a script picks — a test that could send the data anywhere would be
    testing the address it was given rather than the provider's own backend.
    What a script decides is which submodel it is writing, not where: the
    aspect and the id, which are what the address under that server is built
    from.
    """

    data: Any = Field(
        description=(
            "Payload to upload, sent as JSON. Required: an upload with no payload "
            "of its own would store a placeholder the test then asserts against."
        ),
    )
    semantic_id: str | None = Field(
        default=None,
        description=(
            "URN of the aspect model the payload follows, e.g. "
            "'urn:samm:io.catenax.serial_part:3.0.0#SerialPart'. Percent-encoded "
            "into the storage path when given; the submodel is stored directly "
            "under the server when omitted."
        ),
    )
    submodel_id: str | None = Field(
        default=None,
        description=(
            "Id to store the submodel under; a unique 'urn:uuid:<uuid4>' is generated when omitted."
        ),
    )

    @field_validator("semantic_id", mode="before")
    @classmethod
    def _a_blank_aspect_is_no_aspect(cls, value: Any) -> Any:
        """Read a blank aspect URN as the absent one it is.

        A submodel descriptor written next has to name the same URN (CX-0002),
        so the value matters where it is given — but ``semantic_id: ""`` says
        nothing about an aspect model, and treating it as one would put an empty
        segment in the storage path.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("'semantic_id' must be a string")
        return value.strip() or None

    @field_validator("submodel_id", mode="before")
    @classmethod
    def _submodel_id_names_one_resource_under_the_server(cls, value: Any) -> Any:
        """Normalize the id, and refuse one that is an address rather than an id.

        The server is the engine's (``engine.dtr.submodel_base_url``) — an id allowed to
        carry a scheme and host would be the ``url`` input this step
        deliberately does not have, and would send a provider's data somewhere
        the engine never agreed to. An id with a ``/`` in it is a path, and
        would nest the submodel under its own aspect segment rather than name
        it. Surrounding slashes are the caller's punctuation, so ``/x/`` and
        ``x`` name the same submodel.
        """
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("'submodel_id' must be a string")

        candidate = value.strip()
        if "://" in candidate or candidate.startswith("//"):
            raise ValueError(
                "'submodel_id' is stored under the engine's submodel server; "
                f"it cannot be an absolute URL: {candidate!r}"
            )

        trimmed = candidate.strip("/")
        if "/" in trimmed:
            raise ValueError(
                f"'submodel_id' names one submodel under the server, not a path: {candidate!r}"
            )
        return trimmed or None


class UploadBackendDataOutput(StepPayload):
    """Output contract of ``digital-twin/submodel/upload``."""

    backend_url: str = Field(
        description="Full backend URL the data was uploaded to — server and path together."
    )
    source_url: str = Field(
        description=(
            "Base URL of the submodel server the data now lives on, without the path "
            "— the data source an EDC asset is created against."
        )
    )
    path: str = Field(
        description=(
            "Path the data landed on under the server — the percent-encoded aspect URN "
            "and the submodel id, or the submodel id alone when no aspect was given."
        )
    )
    submodel_id: str = Field(
        description=(
            "Id the submodel was stored under, as given or as generated — the "
            "'urn:uuid:<uuid4>' a descriptor and a lookup name it by."
        )
    )
    semantic_id: str | None = Field(
        default=None,
        description=(
            "URN of the aspect model the uploaded payload follows — the same URN the "
            "submodel descriptor pointing at it must carry; null when none was given."
        ),
    )
    response: Any = Field(
        default=None, description="Backend response body, parsed as JSON when it is JSON."
    )


@step("digital-twin/submodel/upload")
class UploadBackendDataStep(BaseStep[UploadBackendDataParams, UploadBackendDataOutput]):
    """Upload sample data to the engine's submodel server, under its aspect and its id.

    The address is the Industry Core one — ``<server>/<encoded semantic_id>/<submodel_id>``,
    and ``<server>/<submodel_id>`` when the payload names no aspect. A script
    that gives no ``submodel_id`` gets a fresh ``urn:uuid:<uuid4>`` — exactly
    like the TCK does — so repeated runs never collide. One that gives an id
    decides where the data lands, which is what a submodel descriptor written
    ahead of the upload, or a second run overwriting the first, needs.

    The address is published in its pieces, because a test needs them apart:
    ``source_url`` is the server an EDC asset is created against, ``path`` is
    what a data plane appends to it, and ``backend_url`` is the two joined — the
    endpoint a submodel descriptor points at. ``submodel_id`` comes back beside
    them rather than only inside the path, so a descriptor, a lookup or a
    delete can name the submodel without cutting the id back out of a URL, and
    ``semantic_id`` comes back so the descriptor step is wired from this step's
    outputs rather than from a URN retyped beside them.

    The server it posts to comes from the engine configuration
    (``engine.dtr.submodel_base_url``); an engine
    without one cannot run this step, and says so rather than posting nowhere.
    """

    params_model = UploadBackendDataParams
    output_model = UploadBackendDataOutput

    async def execute(
        self,
        params: UploadBackendDataParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[UploadBackendDataOutput]:
        source_url = _submodel_server(context, definition)
        submodel_id = params.submodel_id or f"urn:uuid:{uuid.uuid4()}"
        path = _storage_path(params.semantic_id, submodel_id)
        target_url = f"{source_url}/{path}"
        headers = {"Content-Type": "application/json", **params.headers}
        timeout = params.timeout_or(context.config.default_timeout_s)

        async with httpx.AsyncClient() as client:
            resp = await client.post(target_url, json=params.data, headers=headers, timeout=timeout)

        try:
            resp_body = resp.json()
        except (ValueError, TypeError):
            resp_body = resp.text

        return StepOutput(
            value=UploadBackendDataOutput(
                backend_url=target_url,
                source_url=source_url,
                path=path,
                submodel_id=submodel_id,
                semantic_id=params.semantic_id,
                response=resp_body,
            ),
            request=HttpRequest(method="POST", url=target_url, headers=headers, body=params.data),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp_body,
            ),
        )


# ---------------------------------------------------------------------------
# digital-twin/submodel/delete
# ---------------------------------------------------------------------------


class DeleteBackendDataParams(HttpTransportParams):
    """Input contract of ``digital-twin/submodel/delete``.

    The server is the engine's, as it is for the upload; what a delete has to be
    told is which resource under it to remove, and that is the ``path`` the
    upload published — aspect segment and id together. Naming the path rather
    than re-deriving it from ``semantic_id`` and ``submodel_id`` is what lets a
    teardown be wired straight from the upload it undoes, and is the only way to
    delete a submodel whose path an earlier run, or the provider, chose.
    """

    path: str = Field(
        description=(
            "Path of the submodel to delete under the submodel server, relative to "
            "it — the 'path' the upload published."
        ),
    )

    @field_validator("path", mode="before")
    @classmethod
    def _path_names_a_resource_under_the_configured_server(cls, value: Any) -> Any:
        """Normalize the path, and refuse one that names nothing or a server of its own.

        A blank path is not an empty answer but a missing one: it addresses the
        server itself, and a DELETE sent there would ask a provider to drop every
        submodel it holds rather than the one the test uploaded.
        """
        path = _relative_path(value)
        if path is None:
            raise ValueError(
                "'path' is required: name the submodel to delete, e.g. the 'path' "
                "output of 'digital-twin/submodel/upload'"
            )
        return path


@step("digital-twin/submodel/delete")
class DeleteBackendDataStep(BaseStep[DeleteBackendDataParams, DeletionOutput]):
    """Delete one submodel from the engine's submodel server.

    The teardown half of ``digital-twin/submodel/upload``: it removes the
    resource that upload's ``path`` names, on the server the engine is seeded
    with (``engine.dtr.submodel_base_url``).

    The status the server answered with is published as ``status_code``, so a
    teardown can assert that the data was really there (200/204) rather than
    already gone (404) — the same distinction
    ``digital-twin/provider/delete_shell_descriptor`` publishes.
    """

    params_model = DeleteBackendDataParams
    output_model = DeletionOutput

    async def execute(
        self,
        params: DeleteBackendDataParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[DeletionOutput]:
        source_url = _submodel_server(context, definition)
        target_url = f"{source_url}/{params.path}"
        headers = dict(params.headers)
        timeout = params.timeout_or(context.config.default_timeout_s)

        async with httpx.AsyncClient() as client:
            resp = await client.delete(target_url, headers=headers, timeout=timeout)

        try:
            resp_body: Any = resp.json()
        except (ValueError, TypeError):
            resp_body = resp.text

        return StepOutput(
            value=DeletionOutput(status_code=resp.status_code),
            request=HttpRequest(method="DELETE", url=target_url, headers=headers),
            response=HttpResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp_body,
            ),
        )

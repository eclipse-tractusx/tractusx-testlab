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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""FastAPI routes for the package store: upload, list and delete ``.tck`` archives."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.server.storage import InvalidPackageNameError, PackageStorage, new_package_id

#: Starlette before 1.3.1 ignores the ``request.form()`` field and size limits
#: for this content type, so an upload route that parses it can be made to
#: buffer an unbounded body (GHSA, "request.form() limits silently ignored").
_URLENCODED_FORM = "application/x-www-form-urlencoded"


def _is_urlencoded_form(request: Request) -> bool:
    media_type = request.headers.get("content-type", "").split(";", 1)[0]
    return media_type.strip().lower() == _URLENCODED_FORM


class _NoUrlencodedFormRoute(APIRoute):
    """Refuses urlencoded form bodies before FastAPI parses the request.

    FastAPI reads an ``UploadFile`` route's body with ``request.form()`` ahead
    of any dependency, so the refusal has to sit in the route handler itself.
    Uploads are multipart; no package route accepts a urlencoded form.
    """

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        parse_and_handle = super().get_route_handler()

        async def refuse_urlencoded_form(request: Request) -> Response:
            if _is_urlencoded_form(request):
                return JSONResponse(
                    status_code=415,
                    content={
                        "detail": f"Expected multipart/form-data, received {_URLENCODED_FORM}"
                    },
                )
            return await parse_and_handle(request)

        return refuse_urlencoded_form


packages_router = APIRouter(tags=["testlab"], route_class=_NoUrlencodedFormRoute)


def _get_player(request: Request) -> TestlabPlayer:
    return request.app.state.player


def _get_storage(request: Request) -> PackageStorage:
    return request.app.state.storage


# Annotated dependency aliases, shared with the job routes
PlayerDep = Annotated[TestlabPlayer, Depends(_get_player)]
StorageDep = Annotated[PackageStorage, Depends(_get_storage)]


# ──────────────────────────────────────────────────────────────────────
# Package endpoints
# ──────────────────────────────────────────────────────────────────────


@packages_router.post(
    "/packages",
    status_code=201,
    responses={
        400: {"description": "File must be a .tck archive named without a path"},
        413: {"description": "Package exceeds maximum upload size"},
        415: {"description": "Body must be multipart/form-data, not a urlencoded form"},
    },
)
async def upload_package(
    file: UploadFile,
    player: PlayerDep,
    storage: StorageDep,
) -> JSONResponse:
    """Upload a .tck archive; its bare file name gives the package name and version."""
    if not file.filename or not file.filename.endswith(".tck"):
        raise HTTPException(400, "File must be a .tck archive")

    data = await file.read()
    max_bytes = player._config.max_upload_bytes
    if len(data) > max_bytes:
        raise HTTPException(413, f"Package exceeds maximum size of {max_bytes} bytes")

    package_id = new_package_id()
    stem = file.filename.rsplit(".", 1)[0]
    parts = stem.rsplit("-", 1)
    name = parts[0] if parts else stem
    version = parts[1] if len(parts) > 1 else "1.0"

    try:
        pkg = storage.save(package_id, name, version, data)
    except InvalidPackageNameError as exc:
        raise HTTPException(400, "File name must not contain a path") from exc
    return JSONResponse(content=pkg.model_dump(mode="json"), status_code=201)


@packages_router.get("/packages")
async def list_packages(storage: StorageDep) -> JSONResponse:
    """List all uploaded packages."""
    packages = storage.list_packages()
    return JSONResponse(content=[package.model_dump(mode="json") for package in packages])


@packages_router.delete(
    "/packages/{package_id}",
    status_code=204,
    responses={404: {"description": "Package not found"}},
)
async def delete_package(package_id: str, storage: StorageDep) -> None:
    """Delete a stored package."""
    if not storage.delete(package_id):
        raise HTTPException(404, "Package not found")

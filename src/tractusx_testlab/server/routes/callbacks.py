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

"""Callback webhook route for async callback listeners."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import resolve_mock

callback_router = APIRouter(tags=["testlab"])


def _get_callbacks(request: Request) -> CallbackManager:
    return request.app.state.callbacks


CallbacksDep = Annotated[CallbackManager, Depends(_get_callbacks)]


@callback_router.api_route(
    "/callbacks/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
    responses={404: {"description": "No listener registered for the callback path"}},
)
async def callback_webhook(
    path: str,
    request: Request,
    callbacks: CallbacksDep,
) -> JSONResponse:
    """Catch-all endpoint for async callback listeners."""
    full_path = f"/callbacks/{path}"
    method = request.method
    headers = dict(request.headers)
    body = None
    if method in ("POST", "PUT"):
        body = await request.json()

    query_params = dict(request.query_params)
    mock = resolve_mock(
        full_path, method, headers=headers, query_params=query_params, body=body
    )

    # A path no step opened is refused rather than buffered — see the
    # equivalent guard on the app-level catch-all in ``server.app``.
    if mock is None and not callbacks.has_listener(full_path, method):
        raise HTTPException(404, f"No listener registered for {method} {full_path}")

    callbacks.resolve(full_path, method, headers, body, query_params)
    if mock is not None:
        return JSONResponse(
            content=mock.body, status_code=mock.status_code, headers=mock.headers or None
        )

    return JSONResponse(content={"status": "received"})

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

"""Callback webhook route for async callback listeners."""

from __future__ import annotations

import logging
from inspect import isawaitable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.mock_registry import carries_key_of, query_of, refusal, resolve_mock

_logger = logging.getLogger(__name__)

callback_router = APIRouter(tags=["testlab"])


def refused(callbacks: CallbackManager, path: str, method: str, reason: str) -> JSONResponse:
    """Turn away a call that lacks what the mock requires, count it, and fail its wait.

    401 rather than 404: the address exists, and whoever called it should learn
    that it is the credential that is missing — which, for a mock behind a
    connector, means the call did not come through the connector. The expected
    header's name and value are not said, not even in the log.

    The wait on the address ends here, failed with *reason* (``mock_registry``'s
    ``refusal``): the call reached the mock, so the run has its answer and
    waiting out the timeout would only hide it.
    """
    callbacks.refuse(path, method)
    ended = callbacks.reject(path, method, reason)
    _logger.warning(
        "Refused %s %s: %s — it did not come through the connector whose asset "
        "carries the run's key%s",
        method,
        _loggable(path),
        reason,
        "; the wait on it fails" if ended else "",
    )
    return JSONResponse(
        status_code=401,
        content={
            "detail": (
                f"{method} {path} is served only through the connector that offers it: "
                "negotiate the offer and call through the data plane."
            )
        },
    )


def misdirected(callbacks: CallbackManager, path: str, method: str, headers: dict) -> None:
    """Fail the wait a call that reached no mock was meant for, if one can be told.

    The caller is answered 404 either way. What this adds is the run's side of
    it: a call on the address a wait is blocked on, with the wrong method, or
    one carrying the key of the mock a wait is blocked on, on another path, was
    made for that wait — and the wait fails on it now, saying where the call
    went, instead of timing out as though the system under test had never
    called. A call that can be pinned on no wait is only answered.
    """
    for awaited_path, awaited_method in callbacks.awaited():
        if awaited_path != path and not carries_key_of(awaited_path, awaited_method, headers):
            continue
        reason = f"the call went to {method} {path}, not to {awaited_method} {awaited_path}"
        if callbacks.reject(awaited_path, awaited_method, reason):
            _logger.warning(
                "Misdirected %s %s: the wait on %s %s fails",
                method,
                _loggable(path),
                awaited_method,
                _loggable(awaited_path),
            )


def _loggable(path: str) -> str:
    """*path* as it may be logged: bounded, and unable to start a log line of its own."""
    return path[:80].replace("\n", "").replace("\r", "")


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
    reason = refusal(full_path, method, headers)
    if reason is not None:
        return refused(callbacks, full_path, method, reason)
    body = None
    if method in ("POST", "PUT"):
        body = await request.json()

    # Two readings of one query string, for two audiences: a handler is a server
    # and sees every value it was sent, a callback result is what a test reads
    # and carries one value per name (mock_registry.MockRequest).
    query_params = dict(request.query_params)
    mock = resolve_mock(
        full_path,
        method,
        headers=headers,
        query_params=query_of(request.query_params.multi_items()),
        body=body,
    )
    if isawaitable(mock):
        mock = await mock

    # A path no step opened is refused rather than buffered — see the
    # equivalent guard on the app-level catch-all in ``server.app``.
    if mock is None and not callbacks.has_listener(full_path, method):
        misdirected(callbacks, full_path, method, headers)
        raise HTTPException(404, f"No listener registered for {method} {full_path}")

    callbacks.resolve(full_path, method, headers, body, query_params)
    if mock is not None:
        return JSONResponse(
            content=mock.body, status_code=mock.status_code, headers=mock.headers or None
        )

    return JSONResponse(content={"status": "received"})

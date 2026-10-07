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

"""Callback webhook route for async callback listeners, and how every inbound call is answered.

Two routes take calls from the system under test — ``/testlab/callbacks/...``
here and the catch-all on the server root (``server.app``) — and both answer
through :func:`answer`, so a call is treated the same whichever it came in on.
"""

from __future__ import annotations

import logging
from inspect import isawaitable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.inbound.run_scope import declared, split
from tractusx_testlab.server.mock_registry import (
    carries_key_of,
    locate,
    query_of,
    refusal,
    resolve_mock,
)

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
                f"{method} {declared(path)} is served only through the connector that offers "
                "it: negotiate the offer and call through the data plane."
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
    called. A call that can be pinned on no wait is only answered. *path* is
    the key path the call was located at, so only its own run's waits match.
    """
    for awaited_path, awaited_method in callbacks.awaited():
        if awaited_path != path and not carries_key_of(awaited_path, awaited_method, headers):
            continue
        reason = (
            f"the call went to {method} {declared(path)}, "
            f"not to {awaited_method} {declared(awaited_path)}"
        )
        if callbacks.reject(awaited_path, awaited_method, reason):
            _logger.warning(
                "Misdirected %s %s: the wait on %s %s fails",
                method,
                _loggable(path),
                awaited_method,
                _loggable(awaited_path),
            )


def on_hold(app: Any, run: str | None = None) -> bool:
    """Whether the run a call is for is paused on hold (``player.execution.hold``).

    A held run answers nothing: a call is turned away with 404, as for a run
    that is not going, and neither resolves nor fails the wait — which has
    stopped, and starts again with the time it had left once the run resumes.
    A call located at a run of this server's player is held with that run
    alone; one that names no run of it is held while any of its runs is.
    """
    jobs = getattr(getattr(app.state, "player", None), "jobs", None)
    get, is_held = getattr(jobs, "get", None), getattr(jobs, "is_held", None)
    if run is not None and callable(get) and callable(is_held) and get(run) is not None:
        return is_held(run) is True
    any_held = getattr(jobs, "any_held", None)
    return callable(any_held) and any_held() is True


def held(method: str, path: str) -> HTTPException:
    """The answer to a call made while the run is on hold."""
    return HTTPException(
        404, f"No mock answers {method} {path} while the run is paused; call again once it resumes"
    )


def _loggable(path: str) -> str:
    """*path* as it may be logged: bounded, and unable to start a log line of its own."""
    return path[:80].replace("\n", "").replace("\r", "")


async def answer(request: Request, called: str) -> JSONResponse:
    """Answer an inbound call on *called*, the path it was made on.

    The call is located first — the run's own address, or the one run a bare
    path can be pinned on (``mock_registry.locate``) — and everything after
    reads that run's mock, guard and listener alone. A bare path several runs
    serve, with none of their keys, is answered 409 and touches no run.

    Then, in order: a held run answers nothing; a caller the mock does not
    admit is refused before any handler runs and before the listener is
    resolved, so the call cannot stand in for the one the test waits on; a path
    nobody opened is 404 rather than buffered — ``resolve`` buffers a call
    nothing is waiting for, which is right when the SUT beats the test to its
    own wait step and wrong for an address that was never registered.
    """
    method = request.method
    headers = dict(request.headers)
    callbacks: CallbackManager = request.app.state.callbacks
    path = locate(called, headers)
    if path is None:
        raise HTTPException(
            409, f"More than one run serves {method} {called}; call the address the run published"
        )
    if on_hold(request.app, split(path)[0]):
        raise held(method, called)
    body = None
    if method in ("POST", "PUT"):
        try:
            body = await request.json()
        except ValueError:
            body = {}

    reason = refusal(path, method, headers)
    if reason is not None:
        return refused(callbacks, path, method, reason)

    # Two readings of one query string, for two audiences: a handler is a server
    # and sees every value it was sent, a callback result is what a test reads
    # and carries one value per name (mock_registry.MockRequest).
    mock = resolve_mock(
        path,
        method,
        headers=headers,
        query_params=query_of(request.query_params.multi_items()),
        body=body,
    )
    if isawaitable(mock):
        mock = await mock

    if mock is None and not callbacks.has_listener(path, method):
        misdirected(callbacks, path, method, headers)
        raise HTTPException(404, f"No mock or listener for {method} {called}")

    matched = callbacks.resolve(path, method, headers, body, dict(request.query_params))
    if mock is not None:
        _logger.debug("Mock matched %s %s -> %d", method, _loggable(path), mock.status_code)
        return JSONResponse(
            content=mock.body, status_code=mock.status_code, headers=mock.headers or None
        )
    if matched:
        return JSONResponse(content={"status": "received"})
    raise HTTPException(404, f"No mock or listener for {method} {called}")


@callback_router.api_route(
    "/callbacks/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE"],
    responses={404: {"description": "No listener registered for the callback path"}},
)
async def callback_webhook(path: str, request: Request) -> JSONResponse:
    """Catch-all endpoint for async callback listeners."""
    return await answer(request, f"/callbacks/{path}")


#: What a server that only serves a running job mounts under ``/testlab``: the
#: callback route, and nothing that starts, reads or stops a run.
inbound_router = APIRouter(prefix="/testlab", tags=["testlab"])
inbound_router.include_router(callback_router)

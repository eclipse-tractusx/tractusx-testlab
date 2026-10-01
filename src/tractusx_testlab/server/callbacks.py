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

"""CallbackManager — manages ephemeral HTTP listener endpoints for async callbacks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from tractusx_testlab.logging.wire import safe_headers
from tractusx_testlab.models import CallbackResult


class CallbackManager:
    """Registers temporary HTTP listeners and waits for incoming callbacks.

    Each listener is associated with a ``path`` + ``method`` and blocks until
    a matching request arrives or the timeout elapses.
    """

    __slots__ = ("_awaited", "_buffered", "_listeners", "_loop", "_refused")

    def __init__(self) -> None:
        self._listeners: dict[str, asyncio.Future[CallbackResult]] = {}
        self._buffered: dict[str, CallbackResult] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._refused: dict[str, int] = {}
        self._awaited: set[str] = set()

    def register(self, path: str, method: str) -> None:
        """Prepare a listener slot. The future will be resolved when a request arrives.

        If a matching callback was already buffered (arrived before the listener
        was registered), the future is resolved immediately.
        """
        key = self._key(path, method)
        stale = self._listeners.get(key)
        if stale is not None and _is_stale(stale):
            del self._listeners[key]
        if key not in self._listeners:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            self._loop = loop
            future: asyncio.Future[CallbackResult] = loop.create_future()
            self._listeners[key] = future

            # Check if a callback was buffered before the listener existed
            buffered = self._buffered.pop(key, None)
            if buffered is not None:
                future.set_result(buffered)

    def has_listener(self, path: str, method: str) -> bool:
        """Whether a listener slot exists for *path*/*method*.

        Asked by the inbound routes before they accept a request: ``resolve``
        buffers a call nothing is waiting for and reports success for it, which
        is right for a race between the SUT and the test but wrong for an
        address the test never opened.
        """
        return self._key(path, method) in self._listeners

    async def wait(self, path: str, method: str, timeout_s: float) -> CallbackResult:
        """Block until a callback arrives at *path*/*method* or *timeout_s* elapses."""
        key = self._key(path, method)
        future = self._listeners.get(key)
        if future is None:
            return CallbackResult(
                listener_name=key,
                path=path,
                method=method,
                timed_out=True,
            )

        self._awaited.add(key)
        try:
            result = await asyncio.wait_for(future, timeout=timeout_s)
            return result
        except TimeoutError:
            return CallbackResult(
                listener_name=key,
                path=path,
                method=method,
                timed_out=True,
            )
        finally:
            self._awaited.discard(key)
            self._listeners.pop(key, None)

    def resolve(
        self,
        path: str,
        method: str,
        headers: dict,
        payload: Any,
        query_params: dict | None = None,
    ) -> bool:
        """Called by the webhook route when a request matches a listener.

        Returns True if a listener was waiting or the result was buffered.

        The call's credentials are redacted by header name before anything is
        kept: the mock has already admitted the caller, and what the wait
        returns is published, traced and shown to whoever watches the run.
        """
        key = self._key(path, method)
        result = CallbackResult(
            listener_name=key,
            path=path,
            method=method,
            headers=safe_headers(headers),
            query_params=query_params or {},
            payload=payload,
            received_at=datetime.now(UTC),
        )

        future = self._listeners.get(key)
        if future is not None and not future.done():
            # Thread-safe: resolve may be called from uvicorn's background thread
            # while the future belongs to the main event loop.
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None
            if self._loop is not None and current_loop is not self._loop:
                self._loop.call_soon_threadsafe(future.set_result, result)
            else:
                future.set_result(result)
            return True

        if future is not None and future.done():
            # Listener already resolved/cancelled — cannot deliver
            return False

        # No listener yet — buffer for later registration
        self._buffered[key] = result
        return True

    def refuse(self, path: str, method: str) -> None:
        """Count a call on *path*/*method* the mock turned away.

        It resolves nothing — it is not the call the test waits for — but a
        wait that times out can then say that calls did arrive, and why they
        did not count, instead of implying nothing reached the mock at all.
        """
        key = self._key(path, method)
        self._refused[key] = self._refused.get(key, 0) + 1

    def refused(self, path: str, method: str) -> int:
        """How many calls on *path*/*method* the mock has turned away."""
        return self._refused.get(self._key(path, method), 0)

    def reject(self, path: str, method: str, reason: str) -> bool:
        """End the wait on *path*/*method* with a call that was turned away, and why.

        A call that did not come through the connector, or carried another
        run's key, or went to the wrong address, is a finding about the system
        under test: the wait fails on it now, with the reason, instead of
        running out its timeout as though nothing had arrived.

        Only a listener that is still open is ended; a refusal is never
        buffered, since the address outlives the run that opened it and a
        stray call after the run would otherwise fail the next one. Delivered
        on the loop the listener belongs to, whichever thread refused the call.
        Returns whether a wait was ended.
        """
        key = self._key(path, method)
        future = self._listeners.get(key)
        if future is None or future.done():
            return False
        result = CallbackResult(
            listener_name=key,
            path=path,
            method=method,
            received_at=datetime.now(UTC),
            refused=reason,
        )
        loop = future.get_loop()
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is loop:
            future.set_result(result)
            return True
        try:
            loop.call_soon_threadsafe(_settle, future, result)
        except RuntimeError:
            # The loop is closed: the run that opened the listener has ended.
            return False
        return True

    def awaited(self) -> list[tuple[str, str]]:
        """``(path, method)`` of every call a wait step is blocked on right now.

        Narrower than the open listeners: ``mock/api`` opens one for every mock
        it registers, and a call that reached no mock is attributed only to a
        wait already under way, not to one the test may never reach.
        """
        return [
            (path, method)
            for key in list(self._awaited)
            for method, _, path in [key.partition(":")]
        ]

    def clear(self) -> None:
        """Cancel all pending listeners and clear buffers."""
        for future in self._listeners.values():
            if not future.done():
                future.cancel()
        self._listeners.clear()
        self._buffered.clear()
        self._refused.clear()
        self._awaited.clear()

    @staticmethod
    def _key(path: str, method: str) -> str:
        return f"{method.upper()}:{path}"


def _is_stale(future: asyncio.Future[CallbackResult]) -> bool:
    """Whether a listener left behind cannot serve a mock registered again now.

    One ended by a refused call: the refusal belonged to the wait it was meant
    to fail, and a mock armed afresh on the address starts clean. And one bound
    to a loop that is gone — the run that opened it ended without waiting on
    it, and awaiting it from another run's loop would fail.
    """
    if future.get_loop().is_closed():
        return True
    if not future.done():
        return False
    if future.cancelled() or future.exception() is not None:
        return True
    return future.result().refused is not None


def _settle(future: asyncio.Future[CallbackResult], result: CallbackResult) -> None:
    """Resolve *future* with *result* unless something resolved it first."""
    if not future.done():
        future.set_result(result)

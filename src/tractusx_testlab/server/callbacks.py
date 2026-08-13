#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). 
## It was reviewed and tested by a human committer.

"""CallbackManager — manages ephemeral HTTP listener endpoints for async callbacks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from tractusx_testlab.models import CallbackResult


class CallbackManager:
    """Registers temporary HTTP listeners and waits for incoming callbacks.

    Each listener is associated with a ``path`` + ``method`` and blocks until
    a matching request arrives or the timeout elapses.
    """

    __slots__ = ("_listeners", "_buffered", "_loop")

    def __init__(self) -> None:
        self._listeners: dict[str, asyncio.Future[CallbackResult]] = {}
        self._buffered: dict[str, CallbackResult] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def register(self, path: str, method: str) -> None:
        """Prepare a listener slot. The future will be resolved when a request arrives.

        If a matching callback was already buffered (arrived before the listener
        was registered), the future is resolved immediately.
        """
        key = self._key(path, method)
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
        is right for a race between the SUT and the script but wrong for an
        address the script never opened.
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

        try:
            result = await asyncio.wait_for(future, timeout=timeout_s)
            return result
        except asyncio.TimeoutError:
            return CallbackResult(
                listener_name=key,
                path=path,
                method=method,
                timed_out=True,
            )
        finally:
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
        """
        key = self._key(path, method)
        result = CallbackResult(
            listener_name=key,
            path=path,
            method=method,
            headers=headers,
            query_params=query_params or {},
            payload=payload,
            received_at=datetime.now(timezone.utc),
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

    def clear(self) -> None:
        """Cancel all pending listeners and clear buffers."""
        for future in self._listeners.values():
            if not future.done():
                future.cancel()
        self._listeners.clear()
        self._buffered.clear()

    @staticmethod
    def _key(path: str, method: str) -> str:
        return f"{method.upper()}:{path}"

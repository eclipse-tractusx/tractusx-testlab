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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4).
## It was reviewed and tested by a human committer.

"""Module-level mock endpoint registry and callback manager holder.

Provides a shared registry for mock HTTP responses and a holder for the
active ``CallbackManager`` so that steps can access them without threading
through ``StepContext``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tractusx_testlab.server.callbacks import CallbackManager


@dataclass(frozen=True)
class MockResponse:
    """Canned response for a mock endpoint."""

    status_code: int
    body: Any = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MockRequest:
    """Inbound request data passed to a dynamic mock handler."""

    method: str
    path: str
    headers: dict
    query_params: dict
    body: Any | None


# A dynamic handler computes the response from the inbound request — used by
# protocol-aware mocks (e.g. mock/dtr, mock/discovery) whose reply depends on
# the request path/query/body rather than being a single canned value.
MockHandler = Callable[["MockRequest"], MockResponse]

# path+method -> canned response or dynamic handler
_mock_routes: dict[str, MockResponse | MockHandler] = {}

# Singleton holder for the active CallbackManager
_callback_manager: CallbackManager | None = None


def _key(path: str, method: str) -> str:
    return f"{method.upper()}:{path}"


def register_mock(path: str, method: str, response: MockResponse | MockHandler) -> None:
    """Register a canned response, or a dynamic handler, for the given path and method."""
    _mock_routes[_key(path, method)] = response


def get_mock(path: str, method: str) -> MockResponse | MockHandler | None:
    """Look up a canned response or dynamic handler, or ``None`` if not registered."""
    return _mock_routes.get(_key(path, method))


def resolve_mock(
    path: str, method: str, *, headers: dict, query_params: dict, body: dict | None,
) -> MockResponse | None:
    """Look up a mock and, if it's a dynamic handler, invoke it to get a response."""
    mock = get_mock(path, method)
    if mock is None:
        return None
    if isinstance(mock, MockResponse):
        return mock
    return mock(MockRequest(
        method=method, path=path, headers=headers, query_params=query_params, body=body,
    ))


def remove_mock(path: str, method: str) -> None:
    """Remove a previously registered mock."""
    _mock_routes.pop(_key(path, method), None)


def clear_mocks() -> None:
    """Remove all registered mocks."""
    _mock_routes.clear()


def set_callback_manager(manager: CallbackManager) -> None:
    """Store the active ``CallbackManager`` for step access."""
    global _callback_manager
    _callback_manager = manager


def get_callback_manager() -> CallbackManager | None:
    """Return the active ``CallbackManager``, or ``None``."""
    return _callback_manager


def clear_callback_manager() -> None:
    """Drop the active ``CallbackManager``, cancelling anything waiting on it.

    The manager holds futures bound to the event loop that registered them, so
    one that outlives its loop resolves nothing and reports "attached to a
    different loop" instead. The counterpart to :func:`clear_mocks`: both clear
    the module state a run leaves behind.
    """
    global _callback_manager
    if _callback_manager is not None:
        _callback_manager.clear()
    _callback_manager = None

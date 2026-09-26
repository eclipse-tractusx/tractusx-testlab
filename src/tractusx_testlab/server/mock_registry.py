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

import hmac
from collections.abc import Callable, Iterable
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
    """Inbound request data passed to a dynamic mock handler.

    ``query_params`` is the query as HTTP actually carries it: a multimap, since
    a name may legitimately repeat. It used to be flattened to one value per
    name, which silently dropped every repeat but the last — and a repeated name
    is not an oddity, it is how the AAS API asks for several search criteria
    (``?assetIds=<a>&assetIds=<b>``). A mock that cannot see the second one
    answers a question it was not asked.

    This is deliberately not the shape a *test* reads: ``mock/wait`` publishes
    ``request_query_params`` as one value per name, because a test asserting on
    a callback's ``state`` wants the value and not a list holding it. A handler
    is a server and has to see the request; a result is a value and has to be
    readable.
    """

    method: str
    path: str
    headers: dict
    query_params: dict[str, list[str]]
    body: Any | None

    def query(self, name: str) -> str | None:
        """The value of a parameter given once, or ``None`` if it was not given.

        The first value when a name repeats: a handler asking for one has
        already decided the parameter is single-valued.
        """
        values = self.query_params.get(name) or []
        return values[0] if values else None

    def query_all(self, name: str) -> list[str]:
        """Every value a parameter was given, in the order they arrived."""
        return list(self.query_params.get(name) or [])


def query_of(pairs: Iterable[tuple[str, str]]) -> dict[str, list[str]]:
    """The query string as a handler sees it, from the pairs it was sent as.

    Built from pairs rather than from a mapping because the mapping is where the
    repeats were lost: ``dict(request.query_params)`` keeps the last value for a
    name and discards the rest.
    """
    query: dict[str, list[str]] = {}
    for name, value in pairs:
        query.setdefault(name, []).append(value)
    return query


# A dynamic handler computes the response from the inbound request — used by
# protocol-aware mocks (e.g. mock/dtr, mock/discovery) whose reply depends on
# the request path/query/body rather than being a single canned value.
MockHandler = Callable[["MockRequest"], MockResponse]

# path+method -> canned response or dynamic handler
_mock_routes: dict[str, MockResponse | MockHandler] = {}

# path+method -> (header name, lower-cased; the value a caller must send in it)
_guards: dict[str, tuple[str, str]] = {}

# Singleton holder for the active CallbackManager
_callback_manager: CallbackManager | None = None


def _key(path: str, method: str) -> str:
    return f"{method.upper()}:{path}"


def register_mock(
    path: str,
    method: str,
    response: MockResponse | MockHandler,
    *,
    required_header: tuple[str, str] | None = None,
) -> None:
    """Register a canned response, or a dynamic handler, for the given path and method.

    *required_header* — a ``(name, value)`` pair — is what a caller must send
    to be answered (:func:`require_header`). It is set before the response is,
    so the mock is never reachable without it, and a registration without one
    drops whatever an earlier registration of the path required.
    """
    key = _key(path, method)
    if required_header is None:
        _guards.pop(key, None)
    else:
        require_header(path, method, *required_header)
    _mock_routes[key] = response


def get_mock(path: str, method: str) -> MockResponse | MockHandler | None:
    """Look up a canned response or dynamic handler, or ``None`` if not registered."""
    return _mock_routes.get(_key(path, method))


def resolve_mock(
    path: str,
    method: str,
    *,
    headers: dict,
    query_params: dict[str, list[str]],
    body: dict | None,
) -> MockResponse | None:
    """Look up a mock and, if it's a dynamic handler, invoke it to get a response."""
    mock = get_mock(path, method)
    if mock is None:
        return None
    if isinstance(mock, MockResponse):
        return mock
    return mock(
        MockRequest(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=body,
        )
    )


def require_header(path: str, method: str, header: str, value: str) -> None:
    """Admit a call on *path*/*method* only when it carries *value* in *header*.

    For a mock that stands behind a connector: its address is published, so
    anyone who reads the run can dial it, but only the connector's data plane
    was given the value — it sits in the private data address of the asset the
    system under test negotiates. A call without it did not come through the
    connector, and the mock refuses it rather than let it pass for one that did.
    """
    _guards[_key(path, method)] = (header.lower(), value)


def admits(path: str, method: str, headers: dict) -> bool:
    """Whether a call on *path*/*method* with *headers* may reach the mock.

    ``True`` for a mock nothing was required of. Header names are compared
    without regard to case, as HTTP does; the value in constant time.
    """
    guard = _guards.get(_key(path, method))
    if guard is None:
        return True
    name, expected = guard
    sent = next((str(value) for key, value in headers.items() if str(key).lower() == name), None)
    return sent is not None and hmac.compare_digest(sent.encode(), expected.encode())


def remove_mock(path: str, method: str) -> None:
    """Remove a previously registered mock, and what it required of a caller."""
    _mock_routes.pop(_key(path, method), None)
    _guards.pop(_key(path, method), None)


def clear_mocks() -> None:
    """Remove all registered mocks, and what they required of a caller."""
    _mock_routes.clear()
    _guards.clear()


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

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Module-level mock endpoint registry and callback manager holder.

Provides a shared registry for mock HTTP responses and a holder for the
active ``CallbackManager`` so that steps can access them without threading
through ``StepContext``. What a mock requires of a caller — the run's key —
lives in ``mock_keys``; which run a call is for, in ``inbound.run_scope``.

Every mock is kept under its run's address (``run_scope.scoped``), so two runs
that register one path keep two mocks. A step registers by the path the test
wrote and names its run — or leaves it to the run whose step is executing
(``run_scope.acting_for``). A lookup takes either the run's address or the bare
path, and first works out whose mock is meant (:func:`locate`).
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING

from tractusx_testlab.server import mock_keys

# The request and response types, re-exported: callers ask this module for them.
from tractusx_testlab.server.inbound.messages import (
    MockHandler,
    MockRequest,
    MockResponse,
    query_of,
)
from tractusx_testlab.server.inbound.run_scope import current_run, declared, pick, scoped, split

# The key half of the registry, re-exported: callers ask this module for both.
from tractusx_testlab.server.mock_keys import (
    MISSING_KEY,
    WRONG_KEY,
    _key,
    _mint_key,
    clear_guards,
    drop_guard,
    require_header,
    run_key,
)

if TYPE_CHECKING:
    from tractusx_testlab.server.callbacks import CallbackManager

#: Why a call on a bare path is turned away when more than one run serves that
#: path and the call carries none of their keys: there is no telling whose it is.
UNADDRESSED = "the call named no run, and more than one run serves that address"

# key path+method -> canned response or dynamic handler
_mock_routes: dict[str, MockResponse | MockHandler] = {}

__all__ = [
    "MISSING_KEY",
    "UNADDRESSED",
    "WRONG_KEY",
    "MockHandler",
    "MockRequest",
    "MockResponse",
    "_mint_key",
    "admits",
    "carries_key_of",
    "clear_callback_manager",
    "clear_mocks",
    "get_callback_manager",
    "get_mock",
    "locate",
    "query_of",
    "refusal",
    "register_mock",
    "release_mocks",
    "remove_mock",
    "require_header",
    "required_header",
    "resolve_mock",
    "run_key",
    "set_callback_manager",
]

# Singleton holder for the active CallbackManager
_callback_manager: CallbackManager | None = None


def register_mock(
    path: str,
    method: str,
    response: MockResponse | MockHandler,
    *,
    required_header: tuple[str, str] | None = None,
    run: str | None = None,
) -> None:
    """Register a canned response, or a dynamic handler, for the given path and method.

    *required_header* — a ``(name, value)`` pair — is what a caller must send
    to be answered (:func:`require_header`). It is set before the response is,
    so the mock is never reachable without it, and a registration without one
    drops whatever an earlier registration of the path required.

    *run* is the run the mock belongs to; unnamed, it is the run whose step is
    executing. A mock registered outside any run is kept at *path* itself.
    """
    key_path = scoped(run or current_run(), path)
    if required_header is None:
        drop_guard(key_path, method)
    else:
        require_header(key_path, method, *required_header)
    _mock_routes[_key(key_path, method)] = response


def locate(path: str, headers: dict | None = None) -> str | None:
    """The key path a call on *path* is for, or ``None`` when no one run can be told.

    *path* is a run's address or a bare path; *headers* are the call's, read for
    the key that names its run when several runs serve a bare path
    (``run_scope.pick``). Asked again with the key path it returned, it returns
    the same one.
    """
    registered = {key.partition(":")[2] for key in list(_mock_routes)}
    registered.update(mock_keys.guarded())
    listening = getattr(_callback_manager, "listening", None)
    if callable(listening):
        registered.update(listened for listened, _ in listening())
    return pick(
        path, registered, lambda key_path: mock_keys.carries_any_key_of(key_path, headers or {})
    )


def get_mock(
    path: str, method: str, *, run: str | None = None
) -> MockResponse | MockHandler | None:
    """Look up a canned response or dynamic handler, or ``None`` if not registered.

    The mock of *run* when it is named, else the one :func:`locate` finds.
    """
    key_path = scoped(run, path) if run else locate(path)
    return None if key_path is None else _mock_routes.get(_key(key_path, method))


def resolve_mock(
    path: str,
    method: str,
    *,
    headers: dict,
    query_params: dict[str, list[str]],
    body: dict | None,
) -> MockResponse | Awaitable[MockResponse] | None:
    """Look up a mock and, if it's a dynamic handler, invoke it (the caller awaits an async one).

    The handler is told the path the test registered, whichever address the
    call came in on.
    """
    key_path = locate(path, headers)
    mock = None if key_path is None else _mock_routes.get(_key(key_path, method))
    if mock is None or isinstance(mock, MockResponse):
        return mock
    return mock(
        MockRequest(
            method=method,
            path=declared(key_path or path),
            headers=headers,
            query_params=query_params,
            body=body,
        )
    )


def required_header(path: str, method: str, *, run: str | None = None) -> tuple[str, str] | None:
    """The ``(name, value)`` a call on *path*/*method* must carry, or ``None``.

    Read by the step that fronts a mock with a connector asset: it hands the
    same pair to the asset's data address, so the data plane sends what the
    mock requires without the test ever naming the key. The mock is *run*'s —
    the executing step's run's when unnamed — and otherwise the one
    :func:`locate` finds for a call that carries no key.
    """
    owner = run or current_run()
    key_path = scoped(owner, path) if owner else locate(path)
    return None if key_path is None else mock_keys.required_header(key_path, method)


def refusal(path: str, method: str, headers: dict) -> str | None:
    """Why a call on *path*/*method* with *headers* may not reach the mock, or ``None``.

    ``mock_keys.refusal`` for the mock the call is for; :data:`UNADDRESSED`
    when there is no telling which run's that is.
    """
    key_path = locate(path, headers)
    if key_path is None:
        return UNADDRESSED
    return mock_keys.refusal(key_path, method, headers)


def admits(path: str, method: str, headers: dict) -> bool:
    """Whether a call on *path*/*method* with *headers* may reach the mock it is for."""
    return refusal(path, method, headers) is None


def carries_key_of(path: str, method: str, headers: dict) -> bool:
    """Whether *headers* carry the key of the mock on *path*/*method* (``mock_keys``)."""
    key_path = locate(path, headers)
    return key_path is not None and mock_keys.carries_key_of(key_path, method, headers)


def remove_mock(path: str, method: str, *, run: str | None = None) -> None:
    """Remove a previously registered mock, and what it required of a caller.

    The mock of *run* — of the executing step's run when unnamed.
    """
    key_path = scoped(run or current_run(), path)
    _mock_routes.pop(_key(key_path, method), None)
    drop_guard(key_path, method)


def release_mocks(run: str) -> None:
    """Remove every mock run *run* registered, what they required, and its listeners.

    Called once the run's records close. Its address keeps nothing after it: a
    call there is answered as one to an address nobody opened, and the registry
    does not grow with every run a long-lived process serves. Every other run's
    mocks, on the same paths or not, stay as they are.
    """
    for key in list(_mock_routes):
        if split(key.partition(":")[2])[0] == run:
            _mock_routes.pop(key, None)
    mock_keys.drop_guards_of(run)
    forget = getattr(_callback_manager, "forget_run", None)
    if callable(forget):
        forget(run)


def clear_mocks() -> None:
    """Remove all registered mocks, and what they required of a caller."""
    _mock_routes.clear()
    clear_guards()


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

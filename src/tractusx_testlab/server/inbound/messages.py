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

"""What an inbound call carries to a mock, and what the mock answers with.

Moved here from ``mock_registry``, which still re-exports every name: a step,
a handler and a test keep importing them from where they always did.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any


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

    ``path`` is the path the mock was registered on, as the test wrote it —
    never the run's own address prefix (``run_scope``), whichever of the two
    addresses the call came in on.
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
# the request path/query/body rather than being a single canned value. One
# that runs steps (labs/mock/api/dynamic) answers asynchronously.
MockHandler = Callable[["MockRequest"], MockResponse | Awaitable[MockResponse]]

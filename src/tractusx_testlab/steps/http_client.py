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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The one way a step makes an HTTP call.

Steps used to reach for ``requests`` — synchronous — from inside ``async def
execute``. Each call held the event loop for its whole duration, and that loop
also runs the in-process callback server. A step waiting on a slow registry
therefore stopped the SUT's callbacks from being answered: with a step timeout
of 600 seconds, the server could be unreachable for ten minutes while the script
sat waiting for a callback that could not arrive.

Two modules already used ``httpx.AsyncClient`` for the same job, so both patterns
were present and neither was canonical. This is the canonical one.
"""

from __future__ import annotations

from typing import Any

import httpx


async def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: Any = None,
    data: dict[str, Any] | None = None,
    content: bytes | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float | None = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    """Make one HTTP request without blocking the event loop.

    A client per call rather than a pooled one: a TCK makes tens of requests,
    not thousands, and a shared client would need a lifecycle tied to the run —
    which is a thing to get wrong for a benefit nothing here can measure.
    """
    async with httpx.AsyncClient(follow_redirects=follow_redirects) as client:
        return await client.request(
            method.upper(),
            url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            content=content,
            auth=auth,
            timeout=timeout,
        )


def body_of(response: httpx.Response) -> Any:
    """Return a response body as JSON when the server said it was JSON.

    Steps report whatever the counterpart sent, so a body that does not parse
    stays text rather than becoming an error: what a SUT answered is the
    evidence, and mangling it would be reporting on something else.
    """
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        return response.text
    try:
        return response.json()
    except ValueError:
        return response.text


def headers_of(response: httpx.Response) -> dict[str, str]:
    """Return a response's headers with the casing the server actually sent.

    ``dict(response.headers)`` lower-cases every name, because httpx's own
    lookups are case-insensitive and it normalises for them. A script does not
    get that courtesy: a TCK reading ``response_headers.X-Next-Cursor`` finds
    nothing once the key has become ``x-next-cursor``.

    ``requests`` preserved the wire casing, so lower-casing here would change
    what existing TCKs read while claiming only to change the transport. The
    raw pairs carry the original names.
    """
    return {name.decode("latin-1"): value.decode("latin-1") for name, value in response.headers.raw}

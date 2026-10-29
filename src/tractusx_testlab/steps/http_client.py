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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The one way a step makes an HTTP call.

Steps used to reach for ``requests`` — synchronous — from inside ``async def
execute``. Each call held the event loop for its whole duration, and that loop
also runs the in-process callback server. A step waiting on a slow registry
therefore stopped the SUT's callbacks from being answered: with a step timeout
of 600 seconds, the server could be unreachable for ten minutes while the test
sat waiting for a callback that could not arrive.

Two modules already used ``httpx.AsyncClient`` for the same job, so both patterns
were present and neither was canonical. This is the canonical one.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

import httpx
from tractusx_sdk.dataspace.tools import trace_call
from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.logging import wire
from tractusx_testlab.models.primitives.exceptions import ExecutionError


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
    secret_headers: Collection[str] = (),
    max_response_bytes: int | None = None,
) -> httpx.Response:
    """Make one HTTP request without blocking the event loop.

    A client per call rather than a pooled one: a TCK makes tens of requests,
    not thousands, and a shared client would need a lifecycle tied to the run —
    which is a thing to get wrong for a benefit nothing here can measure.

    Every call is recorded into the trace the step is being recorded into —
    including one that raises, which is the case a trace is read for.
    ``trace_call`` is the SDK's own instrumentation point, used here so the
    engine's calls and the SDK's land in one ordered list: it records the
    request before sending it, completes the entry with the response or with the
    exception, and does nothing at all outside a step. See
    :mod:`tractusx_testlab.logging.wire`.

    *secret_headers* names headers carrying a credential under a name the
    tracer would not recognise; they are recorded as ``***`` and sent as given.

    *max_response_bytes* bounds the decoded body: it is read in chunks and the
    call fails with :class:`ResponseTooLargeError` past the limit, so a server
    cannot make the run hold an unbounded answer — or a compressed one that
    expands to it.
    """
    traced_headers = (
        {k: REDACTED_VALUE if k in secret_headers else v for k, v in headers.items()}
        if headers and secret_headers
        else headers
    )
    async with httpx.AsyncClient(follow_redirects=follow_redirects) as client:
        with trace_call(
            method.upper(),
            str(url),
            headers=traced_headers,
            params=params,
            body=json if json is not None else data or content,
            context=wire.ENGINE_CONTEXT,
        ) as call:
            if max_response_bytes is None:
                response = await client.request(
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
            else:
                sent = client.build_request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    content=content,
                    timeout=timeout,
                )
                response = await _bounded(client, sent, auth, max_response_bytes)
            call.set_response(response)
        return response


class ResponseTooLargeError(ExecutionError):
    """The server answered with more than the step reads."""

    code = "RESPONSE_TOO_LARGE"

    def __init__(self, url: str, limit: int) -> None:
        self.diagnostics = {"url": url, "limit_bytes": limit}
        super().__init__(f"The answer from {url} is larger than {limit} bytes; it was not read.")


async def _bounded(
    client: httpx.AsyncClient,
    sent: httpx.Request,
    auth: tuple[str, str] | None,
    limit: int,
) -> httpx.Response:
    """Send *sent* and read at most *limit* decoded bytes of the answer."""
    streamed = await client.send(sent, auth=auth, stream=True)
    chunks: list[bytes] = []
    size = 0
    try:
        async for chunk in streamed.aiter_bytes():
            size += len(chunk)
            if size > limit:
                raise ResponseTooLargeError(str(sent.url), limit)
            chunks.append(chunk)
    finally:
        await streamed.aclose()
    # The body is decoded already, so the headers that described the encoding go.
    headers = [
        (name, value)
        for name, value in streamed.headers.raw
        if name.lower() not in (b"content-encoding", b"content-length", b"transfer-encoding")
    ]
    return httpx.Response(
        streamed.status_code, headers=headers, content=b"".join(chunks), request=sent
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
    lookups are case-insensitive and it normalises for them. A test does not
    get that courtesy: a TCK reading ``response_headers.X-Next-Cursor`` finds
    nothing once the key has become ``x-next-cursor``.

    ``requests`` preserved the wire casing, so lower-casing here would change
    what existing TCKs read while claiming only to change the transport. The
    raw pairs carry the original names.
    """
    return {name.decode("latin-1"): value.decode("latin-1") for name, value in response.headers.raw}

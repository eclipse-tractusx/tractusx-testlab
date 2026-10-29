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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""http_client.request with a size cap: a large answer is refused, a small one kept whole."""

from __future__ import annotations

import gzip

import httpx
import pytest

from tractusx_testlab.steps import http_client
from tractusx_testlab.steps.http_client import ResponseTooLargeError

_CLIENT = httpx.AsyncClient


def _serve(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> None:
    monkeypatch.setattr(
        http_client.httpx,
        "AsyncClient",
        lambda **kw: _CLIENT(transport=httpx.MockTransport(lambda _r: response), **kw),
    )


@pytest.mark.asyncio
async def test_an_answer_within_the_cap_is_read_whole(monkeypatch) -> None:
    _serve(monkeypatch, httpx.Response(200, json={"a": 1}, headers={"X-Case": "Kept"}))
    response = await http_client.request("GET", "https://x.test/", max_response_bytes=100)
    assert response.json() == {"a": 1}
    assert http_client.headers_of(response)["X-Case"] == "Kept"


@pytest.mark.asyncio
async def test_an_answer_over_the_cap_is_refused(monkeypatch) -> None:
    _serve(monkeypatch, httpx.Response(200, content=b"x" * 101))
    with pytest.raises(ResponseTooLargeError) as refused:
        await http_client.request("GET", "https://x.test/", max_response_bytes=100)
    assert refused.value.code == "RESPONSE_TOO_LARGE"


@pytest.mark.asyncio
async def test_the_cap_applies_to_the_decoded_body(monkeypatch) -> None:
    bomb = gzip.compress(b"0" * 100_000)
    _serve(monkeypatch, httpx.Response(200, content=bomb, headers={"Content-Encoding": "gzip"}))
    assert len(bomb) < 1_000
    with pytest.raises(ResponseTooLargeError):
        await http_client.request("GET", "https://x.test/", max_response_bytes=10_000)


@pytest.mark.asyncio
async def test_a_decoded_answer_loses_its_encoding_header(monkeypatch) -> None:
    _serve(
        monkeypatch,
        httpx.Response(200, content=gzip.compress(b"hello"), headers={"Content-Encoding": "gzip"}),
    )
    response = await http_client.request("GET", "https://x.test/", max_response_bytes=1_000)
    assert response.text == "hello"
    assert "content-encoding" not in response.headers

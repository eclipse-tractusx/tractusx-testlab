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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Contract tests for ``digital-twin/submodel/upload``.

The submodel server is the engine's, not the script's: what these tests hold to
is that the step reads it from the engine configuration and refuses to run when
there is none, rather than taking an address from whoever wrote the test.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import StepConfigError, StepDefinition
from tractusx_testlab.steps.industry.submodels import UploadBackendDataStep

_USES = "digital-twin/submodel/upload"


def _context(submodel_backend_url: str) -> MagicMock:
    ctx = MagicMock()
    ctx.config = TestlabConfig(submodel_backend_url=submodel_backend_url)
    return ctx


@pytest.mark.asyncio
async def test_it_posts_under_the_configured_server(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_post(self, url, json=None, headers=None, timeout=None):  # noqa: ANN001
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(201, json={"ok": True})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    output = await UploadBackendDataStep().invoke(
        {"data": {"test": True}},
        _context("https://backend.example.com/data/"),
        StepDefinition(id="s", uses=_USES),
    )

    url = str(captured["url"])
    assert url.startswith("https://backend.example.com/data/urn:uuid:")
    assert captured["json"] == {"test": True}
    assert output.value["backend_url"] == url


@pytest.mark.asyncio
async def test_an_engine_without_a_submodel_server_says_so() -> None:
    with pytest.raises(StepConfigError) as error:
        await UploadBackendDataStep().invoke(
            {"data": {"test": True}},
            _context(""),
            StepDefinition(id="s", uses=_USES),
        )

    assert "submodel_backend_url" in str(error.value)

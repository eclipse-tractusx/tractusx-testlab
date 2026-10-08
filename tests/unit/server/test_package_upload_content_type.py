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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.8).
## It was reviewed and tested by a human committer.

"""The package upload refuses urlencoded forms before they are parsed.

Starlette before 1.3.1 ignores ``request.form()`` limits for
``application/x-www-form-urlencoded``; tractusx-sdk holds FastAPI, and with it
Starlette, below the fix, so the route refuses that content type itself.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.server.app import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    (tmp_path / "logs").mkdir()
    config = TestlabConfig(storage_dir=tmp_path / "storage", logs_dir=tmp_path / "logs")
    return TestClient(create_app(config), raise_server_exceptions=False)


@pytest.mark.parametrize(
    "content_type",
    [
        "application/x-www-form-urlencoded",
        "Application/X-WWW-Form-Urlencoded; charset=utf-8",
    ],
)
def test_upload_rejects_a_urlencoded_form_with_415(client: TestClient, content_type: str) -> None:
    response = client.post(
        "/testlab/packages",
        content=b"file=a&" * 1000,
        headers={"content-type": content_type},
    )

    assert response.status_code == 415


def test_upload_never_parses_a_urlencoded_form(client: TestClient) -> None:
    with patch.object(Request, "form", side_effect=AssertionError("form was parsed")) as form:
        client.post(
            "/testlab/packages",
            content=b"file=a",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

    form.assert_not_called()


def test_upload_still_accepts_a_multipart_package(client: TestClient) -> None:
    response = client.post(
        "/testlab/packages",
        files={"file": ("my-tck-1.0.tck", b"PACKAGE", "application/octet-stream")},
    )

    assert response.status_code == 201

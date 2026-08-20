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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Shared fixtures for the test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.services.participants import FileSystemParticipantManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_participants_dir(tmp_path: Path) -> Path:
    """Isolated temp directory for participant storage."""
    d = tmp_path / "participants"
    d.mkdir()
    return d


@pytest.fixture()
def participant_manager(tmp_participants_dir: Path) -> FileSystemParticipantManager:
    """FileSystemParticipantManager backed by a temp directory."""
    return FileSystemParticipantManager(tmp_participants_dir)


def attach_endpoint_url_stubs(ctx: MagicMock) -> MagicMock:
    """Give a StepContext mock string-returning ``get_*_endpoint_url`` methods.

    The real ones read the versioned path off the SDK controller; a mock
    connector service has none, so the base URL, controller name and segments
    are joined instead — enough for steps that only report the URL.
    """

    def _join(base: Any, controller: str, segments: tuple[Any, ...]) -> str:
        root = base.rstrip("/") if isinstance(base, str) else "http://connector"
        return "/".join([root, controller, *(str(segment) for segment in segments)])

    def _consumer_url(controller: str, *segments: Any, service: Any = None) -> str:
        return _join(ctx.dataspace.consumer_base_url(), controller, segments)

    def _provider_url(controller: str, *segments: Any, service: Any = None) -> str:
        return _join(ctx.dataspace.provider_base_url(), controller, segments)

    ctx.dataspace.consumer_endpoint_url = MagicMock(side_effect=_consumer_url)
    ctx.dataspace.provider_endpoint_url = MagicMock(side_effect=_provider_url)
    return ctx


@pytest.fixture()
def mock_context() -> MagicMock:
    """MagicMock of StepContext with working get/set_variable."""
    ctx = attach_endpoint_url_stubs(MagicMock())
    variables: dict[str, Any] = {}
    ctx.variables = variables

    def _set(name: str, value: Any) -> None:
        variables[name] = value

    def _get(name: str, default: Any = None) -> Any:
        return variables.get(name, default)

    def _has(name: str) -> bool:
        return name in variables

    def _get_str(name: str, default: str = "") -> str:
        """Mirrors :meth:`StepContext.get_str` — narrowing, not a second store."""
        value = variables.get(name, default)
        if value is None:
            return default
        return value if isinstance(value, str) else str(value)

    ctx.set_variable = MagicMock(side_effect=_set)
    ctx.get_variable = MagicMock(side_effect=_get)
    ctx.get_str = MagicMock(side_effect=_get_str)
    ctx.has_variable = MagicMock(side_effect=_has)

    # The real runner, because `flow/if` and `flow/retry` run the steps nested
    # inside them and take the runner from the context rather than importing it
    # (contracts.StepInvoker). A step that contains steps needs something that
    # can run one, and a MagicMock cannot.
    from tractusx_testlab.player.execution.step_runner import run_step

    ctx.invoke_step = run_step
    return ctx


def http_response(
    body: object = None,
    *,
    status: int = 200,
    url: str = "https://example.test",
    headers: dict[str, str] | None = None,
    text: str | None = None,
) -> MagicMock:
    """A stand-in for the ``httpx.Response`` a step now receives.

    Steps read a response through ``steps.http_client``: ``body_of`` looks at
    the content type before parsing, and ``headers_of`` reads the raw pairs to
    keep the casing the server sent. A double therefore has to carry both, which
    is why this lives here rather than being written out per test file.
    """
    sent = {"content-type": "application/json", **(headers or {})}
    response = MagicMock(status_code=status, url=url, text=text or "")
    response.headers = MagicMock(
        raw=[(k.encode(), v.encode()) for k, v in sent.items()],
        **{"get.side_effect": sent.get},
    )
    response.json.return_value = body
    return response

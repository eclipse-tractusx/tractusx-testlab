#################################################################################
# Eclipse Tractus-X - Software Development KIT
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

"""mock/dtr step — a protocol-aware Digital Twin Registry mock.

Registers a small in-memory shell store and wires up the subset of the AAS
Digital Twin Registry API that test scripts typically exercise:

- ``GET  /shell-descriptors``            — list all configured shells
- ``GET  /shell-descriptors/{b64 id}``   — fetch one shell by its (base64url) id
- ``POST /shell-descriptors``            — register a new shell descriptor
- ``GET  /lookup/shells``                — find shell ids by ``specificAssetIds``
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import TYPE_CHECKING

from pydantic import Field

from tractusx_testlab.models import StepDefinition
from tractusx_testlab.scripting.registry import step
from tractusx_testlab.server.mock_registry import MockRequest, MockResponse, register_mock
from tractusx_testlab.steps._contracts import NoOutput
from tractusx_testlab.steps.base import BaseStep, StepOutput
from tractusx_testlab.steps.server._contracts import RequiredMockIdParams

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_BASE_PATH = "/shell-descriptors"
_LOOKUP_PATH = "/lookup/shells"


def _b64url_encode(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> str:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8")


def _matches_asset_ids(shell: dict, requested: list[dict]) -> bool:
    """True if every requested {name, value} pair is present in the shell's specificAssetIds."""
    available = shell.get("specificAssetIds", []) or []
    available_pairs = {(a.get("name"), a.get("value")) for a in available if isinstance(a, dict)}
    return all((r.get("name"), r.get("value")) in available_pairs for r in requested)


class MockDtrParams(RequiredMockIdParams):
    """Input contract of ``mock/dtr``."""

    shells: list[dict] = Field(
        default_factory=list,
        description=(
            "Shell descriptors the registry starts with, each carrying an 'id' "
            "and optionally 'specificAssetIds'."
        ),
    )


@step("mock/dtr")
class MockDtrStep(BaseStep[MockDtrParams, NoOutput]):
    """Register a protocol-aware AAS Digital Twin Registry mock.

    Shells registered through the mock's own ``POST /shell-descriptors`` become
    retrievable the same way the pre-configured ones are, so a script can
    exercise the write path and the read path against one registry.
    """

    params_model = MockDtrParams
    output_model = NoOutput

    async def execute(
        self, params: MockDtrParams, context: "StepContext", definition: StepDefinition,
    ) -> StepOutput[NoOutput]:
        shells: list[dict] = list(params.shells)

        def _list_shells(_req: MockRequest) -> MockResponse:
            return MockResponse(status_code=200, body={"result": shells, "paging_metadata": {}})

        def _get_shell(encoded_id: str):
            def _handler(_req: MockRequest) -> MockResponse:
                try:
                    shell_id = _b64url_decode(encoded_id)
                except (binascii.Error, ValueError):
                    return MockResponse(status_code=400, body={"error": "invalid identifier encoding"})
                found = next((s for s in shells if s.get("id") == shell_id), None)
                if found is None:
                    return MockResponse(status_code=404, body={"error": f"shell '{shell_id}' not found"})
                return MockResponse(status_code=200, body=found)
            return _handler

        def _register_shell(req: MockRequest) -> MockResponse:
            descriptor = req.body or {}
            shells.append(descriptor)
            register_mock(
                f"{_BASE_PATH}/{_b64url_encode(descriptor.get('id', ''))}", "GET",
                _get_shell(_b64url_encode(descriptor.get("id", ""))),
            )
            return MockResponse(status_code=201, body=descriptor)

        def _lookup_shells(req: MockRequest) -> MockResponse:
            raw = req.query_params.get("assetIds")
            if not raw:
                return MockResponse(status_code=200, body={"result": [s.get("id") for s in shells]})
            try:
                requested = json.loads(_b64url_decode(raw))
            except (binascii.Error, ValueError, json.JSONDecodeError):
                return MockResponse(status_code=400, body={"error": "invalid assetIds encoding"})
            matches = [s.get("id") for s in shells if _matches_asset_ids(s, requested)]
            return MockResponse(status_code=200, body={"result": matches})

        register_mock(_BASE_PATH, "GET", _list_shells)
        register_mock(_BASE_PATH, "POST", _register_shell)
        register_mock(_LOOKUP_PATH, "GET", _lookup_shells)
        for shell in shells:
            shell_id = shell.get("id")
            if shell_id:
                register_mock(f"{_BASE_PATH}/{_b64url_encode(shell_id)}", "GET", _get_shell(_b64url_encode(shell_id)))

        logger.info(
            "Registered mock DTR '%s' with %d pre-configured shells", params.id, len(shells)
        )
        return StepOutput(value=NoOutput(None))

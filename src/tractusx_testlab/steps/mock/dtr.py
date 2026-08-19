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
from tractusx_testlab.steps.mock._models import RequiredMockIdParams
from tractusx_testlab.steps.shared_models import NoOutput
from tractusx_testlab.steps.step_contract import BaseStep, StepOutput

if TYPE_CHECKING:
    from tractusx_testlab.player.execution.context import StepContext

logger = logging.getLogger(__name__)

_BASE_PATH = "/shell-descriptors"
_LOOKUP_PATH = "/lookup/shells"
_LOOKUP_BY_ASSET_LINK_PATH = "/lookup/shellsByAssetLink"

#: The query parameter ``GET /lookup/shells`` takes its criteria in, one value
#: per criterion.
_ASSET_IDS_PARAM = "assetIds"


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

    It answers the AAS v3 API as a real registry does, which is what makes it
    worth testing against: ``GET /lookup/shells`` takes one ``assetIds`` value
    per criterion, each a base64url-encoded ``SpecificAssetId`` object, and a
    value holding the whole list is refused with a 400 that says so. The
    consumer-side steps already send it that way, so a script that uses them
    needs to know none of this.
    """

    params_model = MockDtrParams
    output_model = NoOutput

    async def execute(
        self,
        params: MockDtrParams,
        context: StepContext,
        definition: StepDefinition,
    ) -> StepOutput[NoOutput]:
        shells: list[dict] = list(params.shells)

        def _list_shells(_req: MockRequest) -> MockResponse:
            return MockResponse(status_code=200, body={"result": shells, "paging_metadata": {}})

        def _get_shell(encoded_id: str):
            def _handler(_req: MockRequest) -> MockResponse:
                try:
                    shell_id = _b64url_decode(encoded_id)
                except (binascii.Error, ValueError):
                    return MockResponse(
                        status_code=400, body={"error": "invalid identifier encoding"}
                    )
                found = next((s for s in shells if s.get("id") == shell_id), None)
                if found is None:
                    return MockResponse(
                        status_code=404, body={"error": f"shell '{shell_id}' not found"}
                    )
                return MockResponse(status_code=200, body=found)

            return _handler

        def _register_shell(req: MockRequest) -> MockResponse:
            descriptor = req.body or {}
            shells.append(descriptor)
            register_mock(
                f"{_BASE_PATH}/{_b64url_encode(descriptor.get('id', ''))}",
                "GET",
                _get_shell(_b64url_encode(descriptor.get("id", ""))),
            )
            return MockResponse(status_code=201, body=descriptor)

        def _lookup_shells(req: MockRequest) -> MockResponse:
            """The query-carried spelling of the lookup, as AAS v3 defines it.

            One ``assetIds`` value per criterion, each a base64url-encoded
            SpecificAssetId **object** — not one value holding the whole list.
            That is what a real registry reads and what this engine's own
            ``digital-twin-registry/consumer/dataplane/lookup_shell`` sends
            (``registry_models._asset_ids_query``); a mock that read the list
            form answered a request no AAS client makes and failed every request
            they do make. No criteria at all matches every shell, the way an
            absent ``assetIds`` does.
            """
            raw = req.query_all(_ASSET_IDS_PARAM)
            if not raw:
                return MockResponse(status_code=200, body={"result": [s.get("id") for s in shells]})
            try:
                requested = [json.loads(_b64url_decode(value)) for value in raw]
            except (binascii.Error, ValueError, json.JSONDecodeError):
                return MockResponse(status_code=400, body={"error": "invalid assetIds encoding"})
            if not all(isinstance(entry, dict) for entry in requested):
                # The list-in-one-value spelling lands here. Refusing it by name
                # is the point: a script that built the query by hand is told
                # which encoding the endpoint takes, instead of being answered
                # as though it had asked for something.
                return MockResponse(
                    status_code=400,
                    body={
                        "error": (
                            "each 'assetIds' value must be one base64url-encoded "
                            "SpecificAssetId object; repeat the parameter for "
                            "several criteria"
                        )
                    },
                )
            matches = [s.get("id") for s in shells if _matches_asset_ids(s, requested)]
            return MockResponse(status_code=200, body={"result": matches})

        def _lookup_shells_by_asset_link(req: MockRequest) -> MockResponse:
            """The body-carried spelling of the same lookup.

            ``POST /lookup/shellsByAssetLink`` takes the criteria as a plain JSON
            array, so there is nothing to decode and no query-length limit — an
            empty array matches every shell, the way an absent ``assetIds`` does.
            """
            requested = req.body if isinstance(req.body, list) else None
            if requested is None:
                return MockResponse(
                    status_code=400, body={"error": "body must be a list of asset links"}
                )
            matches = [s.get("id") for s in shells if _matches_asset_ids(s, requested)]
            return MockResponse(status_code=200, body={"result": matches, "paging_metadata": {}})

        register_mock(_BASE_PATH, "GET", _list_shells)
        register_mock(_BASE_PATH, "POST", _register_shell)
        register_mock(_LOOKUP_PATH, "GET", _lookup_shells)
        register_mock(_LOOKUP_BY_ASSET_LINK_PATH, "POST", _lookup_shells_by_asset_link)
        for shell in shells:
            shell_id = shell.get("id")
            if shell_id:
                register_mock(
                    f"{_BASE_PATH}/{_b64url_encode(shell_id)}",
                    "GET",
                    _get_shell(_b64url_encode(shell_id)),
                )

        logger.info(
            "Registered mock DTR '%s' with %d pre-configured shells", params.id, len(shells)
        )
        return StepOutput(value=NoOutput(None))

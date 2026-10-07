################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A SUT connector key with no management URL is a handle nothing can open.

A counter-party's connector is bound by its DSP endpoint alone; the management
URL — the one address its key is presented to — is optional on that side. An
operator who states the key without it gets a handle bound to no origin at all,
and such a handle is released to no request, whatever the URL and whichever
sides the run releases: not to the connector's DSP endpoint, not to the mock
server, not to anything a test could name.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure.mapping import flatten
from tractusx_testlab.models import Job, StepDefinition
from tractusx_testlab.models.domain.capabilities import SutConnectorBinding
from tractusx_testlab.models.domain.infrastructure import Infrastructure, SutBindings
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.security.credentials import Credential, CredentialOriginMismatchError
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.http.request import HttpRequestStep

_KEY = "sut-management-key-0123456789"
_DSP = "https://sut.example.com/api/v1/dsp"
_NAME = "infrastructure.sut.connector.api_key"

#: Every kind of address a test could hand the key to.
_URLS = [
    _DSP,
    "https://sut.example.com/management/v3/assets",
    "https://sut.example.com",
    "http://localhost:8100/runs/run-1/companycertificate/push",
    "https://evil.example.com/collect",
    "",
]


@pytest.fixture()
def handle() -> Credential:
    infrastructure = Infrastructure(
        sut=SutBindings(connector=SutConnectorBinding(dsp_url=_DSP, api_key=_KEY))
    )
    projected = flatten(infrastructure)[_NAME]
    assert isinstance(projected, Credential)
    return projected


def test_the_handle_is_bound_to_no_origin(handle: Credential) -> None:
    assert handle.origins == frozenset()
    assert str(handle) == "***"


@pytest.mark.parametrize("url", _URLS)
def test_it_is_released_to_no_url(handle: Credential, url: str) -> None:
    with pytest.raises(CredentialOriginMismatchError):
        handle.reveal_for(url, {"engine", "sut"})


@pytest.mark.asyncio
async def test_a_request_carrying_it_is_never_sent(handle: Credential) -> None:
    context = StepContext(
        services=ServiceManager(), job=Job(job_id="run-1"), config=TestlabConfig()
    )
    with patch("tractusx_testlab.steps.http_client.request", new_callable=AsyncMock) as request:
        with pytest.raises(CredentialOriginMismatchError):
            await HttpRequestStep().invoke(
                {"url": _DSP, "headers": {"x-api-key": handle}},
                context,
                StepDefinition(id="s", uses="http/http_request"),
            )

    request.assert_not_awaited()

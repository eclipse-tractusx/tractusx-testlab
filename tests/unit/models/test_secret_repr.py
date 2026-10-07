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

"""A config printed, logged or shown in a traceback does not carry its credentials.

``repr()`` is what a log line with ``%r``, a traceback's locals and a debugger
show. The vault token and every binding field marked secret stay out of it —
and stay in a dump, which the engine rebuilds the same models from.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import VaultConfig
from tractusx_testlab.models.domain.capabilities import ConnectorBinding, SutConnectorBinding
from tractusx_testlab.models.domain.infrastructure import (
    EngineBindings,
    Infrastructure,
    SutBindings,
    capability_bindings,
)

_ENGINE_KEY = "engine-management-key-0123456789"
_SUT_KEY = "sut-management-key-9876543210"
_VAULT_TOKEN = "hvs.vault-token-abcdefghijklmnop"


@pytest.fixture()
def config() -> TestlabConfig:
    return TestlabConfig(
        vault=VaultConfig(vault_url="https://vault.example.com", vault_token=_VAULT_TOKEN),
        infrastructure=Infrastructure(
            engine=EngineBindings(
                connector=ConnectorBinding(
                    management_url="https://engine.example.com/management", api_key=_ENGINE_KEY
                )
            ),
            sut=SutBindings(
                connector=SutConnectorBinding(
                    dsp_url="https://sut.example.com/api/v1/dsp", api_key=_SUT_KEY
                )
            ),
        ),
    )


@pytest.mark.parametrize("show", [repr, str])
def test_no_credential_is_shown(config: TestlabConfig, show: Callable[[object], str]) -> None:
    for shown in (show(config), show(config.vault), show(config.infrastructure)):
        assert _ENGINE_KEY not in shown
        assert _SUT_KEY not in shown
        assert _VAULT_TOKEN not in shown
    assert "https://engine.example.com/management" in repr(config)


def test_a_dump_still_carries_them_and_rebuilds_the_same_config(config: TestlabConfig) -> None:
    dumped = config.model_dump()

    assert dumped["vault"]["vault_token"] == _VAULT_TOKEN
    assert dumped["infrastructure"]["engine"]["connector"]["api_key"] == _ENGINE_KEY
    assert TestlabConfig.model_validate(dumped) == config


def test_every_secret_field_is_kept_out_of_repr() -> None:
    """A secret field added later is caught here, not in someone's log."""
    for _side, _capability, binding_type in capability_bindings():
        for name in binding_type.secret_fields():
            assert binding_type.model_fields[name].repr is False, f"{binding_type.__name__}.{name}"

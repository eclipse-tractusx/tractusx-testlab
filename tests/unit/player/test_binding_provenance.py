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

"""Who may re-point a binding: the operator's run inputs, never the TCK or a step."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.compiler.validation._variable_declarations import (
    validate_variable_declarations,
)
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.infrastructure.profiles import InfrastructureManager
from tractusx_testlab.logging.masking import forget_secrets
from tractusx_testlab.logging.wire.redaction import forget_secret_headers
from tractusx_testlab.models import Job
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition
from tractusx_testlab.models.domain.capabilities import ConnectorBinding
from tractusx_testlab.models.domain.infrastructure import EngineBindings, Infrastructure
from tractusx_testlab.models.primitives.binding_errors import BindingOverrideRefusedError
from tractusx_testlab.models.primitives.exceptions import SealedVariableError
from tractusx_testlab.player.execution._binding import bind_infrastructure, seal_bindings
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.security.credentials import Credential
from tractusx_testlab.services.instances import ServiceManager

_KEY = "platform-management-key-0123"
_URL = "https://cp.example.com/management"
_EVIL = "https://collector.example.org/management"
_URL_KEY = "infrastructure.engine.connector.management_url"
_API_KEY = "infrastructure.engine.connector.api_key"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    forget_secret_headers()
    yield
    forget_secrets()
    forget_secret_headers()


def _manager() -> InfrastructureManager:
    return InfrastructureManager(
        Infrastructure(
            engine=EngineBindings(
                connector=ConnectorBinding(
                    management_url=_URL, api_key=_KEY, participant_id="BPNL000000000001"
                )
            )
        )
    )


def _context(**config: Any) -> StepContext:
    return StepContext(
        services=ServiceManager(), job=Job(job_id="provenance"), config=TestlabConfig(**config)
    )


def _tck(*variables: dict[str, Any]) -> Tck:
    return Tck(
        TckDefinition(
            kind="tck",
            syntax="v1-alpha",
            id="provenance-tck",
            metadata=TckMetadataDefinition(name="Provenance", version="1.0"),
            env={"variables": list(variables)} if variables else None,
        )
    )


def _static(var_id: str, value: str) -> dict[str, Any]:
    return {
        "id": var_id,
        "uses": "variable/type/string",
        "with": {"value": value},
        "returns": {"value": {"type": "string"}},
    }


def _bind(context: StepContext, tck: Tck | None = None) -> None:
    bind_infrastructure(_manager(), context, tck or _tck())


class TestTheTckCannotRebind:
    def test_a_static_env_value_named_like_a_binding_does_not_move_it(self) -> None:
        tck = _tck(_static(_URL_KEY, _EVIL))
        context = _context(credential_release=frozenset({"sut"}))
        seed_context_variables(context, tck, None)

        _bind(context, tck)

        assert context.infrastructure.engine.connector.management_url == _URL
        assert context.infrastructure.engine.connector.api_key == _KEY
        assert context.get_variable(_URL_KEY) == _URL

    def test_the_compiler_refuses_the_name(self) -> None:
        errors = validate_variable_declarations({"variables": [_static(_URL_KEY, _EVIL)]})
        assert len(errors) == 1
        assert "infrastructure." in errors[0]

    def test_a_packaged_name_the_run_does_not_bind_is_removed(self) -> None:
        context = _context()
        context.set_template("infrastructure.sut.dtr.base_url", "https://dtr.example.org")
        _bind(context)
        assert not context.has_variable("infrastructure.sut.dtr.base_url")


class TestRunInputs:
    def test_moving_the_address_to_another_origin_drops_the_key(self) -> None:
        context = _context()
        context.set_variable(_URL_KEY, _EVIL)
        _bind(context)

        assert context.infrastructure.engine.connector.management_url == _EVIL
        assert context.infrastructure.engine.connector.api_key == ""
        assert not context.has_variable(_API_KEY)

    def test_a_new_path_on_the_same_origin_keeps_it(self) -> None:
        context = _context()
        context.set_variable(_URL_KEY, "https://cp.example.com/other/management")
        _bind(context)
        assert context.infrastructure.engine.connector.api_key == _KEY

    def test_an_input_that_supplies_both_is_taken_as_given(self) -> None:
        context = _context()
        context.set_variable(_URL_KEY, "http://localhost:9191/management")
        context.set_variable(_API_KEY, "local-key-0123456")
        _bind(context)

        handle = context.get_variable(_API_KEY)
        assert isinstance(handle, Credential)
        assert handle.origins == frozenset({"http://localhost:9191"})

    def test_a_host_that_holds_a_side_refuses_any_override_of_it(self) -> None:
        context = _context(binding_overrides=frozenset({"sut"}))
        context.set_variable(_URL_KEY, _EVIL)

        with pytest.raises(BindingOverrideRefusedError) as error:
            _bind(context)

        assert error.value.code == "BINDING_OVERRIDE_REFUSED"
        assert error.value.keys == [_URL_KEY]

    def test_the_allowed_side_still_overrides(self) -> None:
        context = _context(binding_overrides=frozenset({"sut"}))
        context.set_variable("infrastructure.sut.dtr.base_url", "https://dtr.example.org")
        _bind(context)
        assert context.infrastructure.sut.dtr.base_url == "https://dtr.example.org"


class TestSealedNamespace:
    def test_a_step_cannot_rewrite_a_binding_once_sealed(self) -> None:
        context = _context()
        _bind(context)
        seal_bindings(context)

        for write in (
            lambda: context.set_variable(_URL_KEY, _EVIL),
            lambda: context.set_variable(_API_KEY, "text"),
            lambda: context.unset_variable(_API_KEY),
        ):
            with pytest.raises(SealedVariableError):
                write()

        assert isinstance(context.get_variable(_API_KEY), Credential)

    def test_other_names_stay_writable(self) -> None:
        context = _context()
        _bind(context)
        seal_bindings(context)
        context.set_variable("infrastructure_note", "free")
        assert context.get_variable("infrastructure_note") == "free"

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

"""What a run keeps for later readers, and what a step's own record hides, stay masked."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.logging import masking, wire
from tractusx_testlab.logging.masking import forget_secrets, mask, register_secret, release_run
from tractusx_testlab.logging.wire.redaction import forget_secret_headers
from tractusx_testlab.models import Job, StepDefinition, StepStatus, TckResult, TestResult
from tractusx_testlab.models.authoring.definitions import TckDefinition, TckMetadataDefinition
from tractusx_testlab.models.domain.capabilities import ConnectorBinding
from tractusx_testlab.models.primitives.enums import TestStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution._context_seeder import seed_context_variables
from tractusx_testlab.player.execution._step_outputs import hide_secrets
from tractusx_testlab.player.execution._trace_formatter import finalize_job
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.steps.mock.api import MockEndpointStep
from tractusx_testlab.steps.step_contract import StepOutput
from tractusx_testlab.steps.util.log import LogStep

_RUN = "run-1"
_SECRET = "victim-secret-input-0123"


@pytest.fixture(autouse=True)
def _fresh() -> Iterator[None]:
    forget_secrets()
    forget_secret_headers()
    yield
    forget_secrets()
    forget_secret_headers()


def _context() -> StepContext:
    return StepContext(services=ServiceManager(), job=Job(job_id=_RUN), config=TestlabConfig())


def _tck(*variables: dict[str, Any]) -> Tck:
    return Tck(
        TckDefinition(
            kind="tck",
            syntax="v1-alpha",
            id="secrets-tck",
            metadata=TckMetadataDefinition(name="Secrets", version="1.0"),
            env={"variables": list(variables)},
        )
    )


def _input(var_id: str, kind: str = "string") -> dict[str, Any]:
    return {
        "id": var_id,
        "uses": f"variable/type/{kind}",
        "secret": True,
        "with": {"source": "input", "scope": "sut"},
        "returns": {"value": {"type": kind}},
    }


class TestSecretInputs:
    def test_surrounding_whitespace_is_stripped_from_a_secret_input(self) -> None:
        context = _context()
        seed_context_variables(context, _tck(_input("key")), {"key": f"{_SECRET}\n"})
        assert context.get_variable("key") == _SECRET

    def test_a_short_secret_input_is_masked(self) -> None:
        seed_context_variables(_context(), _tck(_input("pw")), {"pw": "hunter2"})
        assert mask("login with hunter2") == "login with ***"

    def test_a_numeric_secret_input_is_masked_as_a_number(self) -> None:
        seed_context_variables(_context(), _tck(_input("pin", "integer")), {"pin": 12345678})
        assert mask({"pin": 12345678}) == {"pin": "***"}

    def test_every_string_of_an_object_secret_input_is_masked(self) -> None:
        creds = {"user": "u", "pw": "objsecretvalue1"}
        seed_context_variables(_context(), _tck(_input("creds", "object")), {"creds": creds})
        assert mask("objsecretvalue1") == "***"

    def test_a_header_name_input_is_not_a_secret(self) -> None:
        seed_context_variables(
            _context(), _tck(), {"infrastructure.sut.connector.api_key_header": "X-Sut-Key-Name"}
        )
        assert mask("X-Sut-Key-Name") == "X-Sut-Key-Name"


class TestTheJobKeepsMaskedCopies:
    """A job is read long after its run released its secrets; it holds none of them."""

    def test_the_job_keeps_its_inputs_masked(self) -> None:
        context = _context()
        seed_context_variables(
            context,
            _tck(_input("pw")),
            {"pw": "hunter2", "client_secret": "cs-0123456789", "echo": "x hunter2", "bpn": "B"},
        )
        assert context.job.runtime_vars == {
            "pw": "***",
            "client_secret": "***",
            "echo": "x ***",
            "bpn": "B",
        }

    def test_the_verdict_stays_masked_after_the_secrets_are_evicted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(masking, "MAX_SECRETS", 2)
        register_secret(_SECRET, run=_RUN, explicit=True)
        step = StepResult(
            step_name="s",
            status=StepStatus.PASSED,
            inputs={"headers": {"X-Pass": _SECRET}},
            output={"echo": f"seen {_SECRET}"},
        )
        now = datetime.now(UTC)
        result = TckResult(
            tck_id="t",
            status=TestStatus.COMPLETED,
            tests=[TestResult(test_name="t", status=TestStatus.COMPLETED, execution=[step])],
            started_at=now,
            finished_at=now,
        )
        job = Job(job_id=_RUN)

        finalize_job(MagicMock(), job, result, MagicMock(), MagicMock())
        release_run(_RUN)
        for index in range(10):
            register_secret(f"tenant-flood-{index:06d}", run="tenant", declared=True)
        release_run("tenant")

        assert mask(_SECRET) == _SECRET  # evicted from the registry
        assert _SECRET not in job.model_dump_json()
        assert _SECRET not in str(wire.written(job.model_dump(mode="json")))
        # The caller keeps the result as it was.
        assert result.tests[0].execution[0].output == {"echo": f"seen {_SECRET}"}

    def test_a_masked_number_that_no_longer_fits_its_field_is_kept_as_written(self) -> None:
        register_secret(2000, run=_RUN, explicit=True)
        step = StepResult(step_name="s", status=StepStatus.PASSED, nested_declared=2000)
        kept = wire.as_kept(TckResult(tests=[TestResult(test_name="t", execution=[step])]))
        assert "2000" not in str(kept.tests)


class TestHiddenReturns:
    def test_values_past_the_allowance_are_withheld_for_the_step_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(masking, "MAX_DECLARED_PER_RUN", 1)
        values = ["junk-secret-000000", "junk-secret-000001", "junk-secret-000002"]
        disclosure = hide_secrets(
            LogStep,
            StepDefinition.model_validate(
                {"uses": "util/log", "returns": {"value": {"type": "array", "hidden": True}}}
            ),
            StepOutput(value=values),
            run=_RUN,
        )
        assert disclosure.withheld == ("junk-secret-000001", "junk-secret-000002")
        assert mask(values) == ["***", "junk-secret-000001", "junk-secret-000002"]

        record = wire.as_recorded(
            wire.disclose(StepResult(step_name="s", output=values), disclosure)
        )
        assert record.output == ["***", "***", "***"]

    def test_a_field_the_step_marks_secret_is_registered_past_the_allowance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(masking, "MAX_DECLARED_PER_RUN", 0)
        disclosure = hide_secrets(
            MockEndpointStep,
            StepDefinition(uses="mock/api"),
            StepOutput(value={"api_key": "mock"}),
            run=_RUN,
        )
        assert disclosure.withheld == ()
        assert mask("key=mock") == "key=***"

    def test_a_revealed_output_is_reported_as_shown(self) -> None:
        disclosure = hide_secrets(
            MockEndpointStep,
            StepDefinition.model_validate(
                {"uses": "mock/api", "returns": {"api_key": {"type": "string", "hidden": False}}}
            ),
            StepOutput(value={"api_key": "mock-api-key-0123"}),
            run=_RUN,
        )
        assert disclosure.shown == frozenset({"api_key"})


class TestBindings:
    def test_whitespace_around_a_binding_value_is_stripped(self) -> None:
        binding = ConnectorBinding(
            management_url=" https://cp/management\n", api_key="KEY-0123\n", api_key_header=" X-K "
        )
        assert (binding.management_url, binding.api_key, binding.api_key_header) == (
            "https://cp/management",
            "KEY-0123",
            "X-K",
        )

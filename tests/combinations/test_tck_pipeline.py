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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.


"""The whole pipeline, on one TCK: author it, compile it, run combinations of it.

Everything else here starts from step dicts or a parsed script. This starts
from files on disk and goes through the commands an operator actually runs —
``validate``, ``compile``, ``inspect``, ``run`` — because each of those is a
place a TCK can be lost between being written and being executed, and none of
them is exercised by testing the pieces.

What it holds to:

* a TCK with several tests compiles into one sealed package, and the package
  carries every test the manifest declared;
* at run time a value published by a setup step reaches an execution step, and
  one published by execution reaches teardown — with the value that arrives
  being the value that was published, checked against the wire the SUT saw;
* every assertion is evaluated and recorded against the step that declared it;
* the verdict the run reports is the verdict its steps earned;
* one compiled package runs as different *combinations* — the selection is a
  run-time argument, and a selection the manifest does not permit is refused.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from combinations.http_double import HttpDouble
from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import ScriptStatus, StepStatus
from tractusx_testlab.models.primitives.exceptions import SkipNotAllowedError
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.player.loading.loader import Loader
from tractusx_testlab.scripting import _inspection

#: Applied per class: the compile-side checks below are synchronous, and a
#: module-wide asyncio mark warns on every one of them.
_ASYNC = pytest.mark.asyncio

_TCK_ID = "pipeline-tck"


def _manifest() -> str:
    return textwrap.dedent(
        f"""
        kind: tck
        syntax: v1-alpha
        id: {_TCK_ID}
        metadata:
          name: Pipeline TCK
          version: v1.0.0
          description: A TCK that exercises the pipeline end to end.
          authors:
            - name: TestLab Maintainers
              email: testlab@eclipse-tractusx.org
              company: Eclipse Tractus-X
          copyright_holders:
            - "2026 Contributors to the Eclipse Foundation"
          license: Apache-2.0
          standards:
            - id: TESTLAB-INTERNAL
              version: v1.0.0
        dataspace:
          ecosystem: Catena-X
          version: saturn
        env:
          variables:
            - id: part_number
              uses: variable/type/string
              with:
                source: value
                value: "PART-4711"
              returns:
                value:
                  type: string
        tests:
          - id: wiring.yaml
            name: Values carried across phases
            skippable: true
          - id: checks.yaml
            name: Assertions recorded per step
            skippable: true
          - id: required.yaml
            name: A test the operator may not omit
        """
    ).lstrip()


def _wiring_test(base_url: str) -> str:
    """setup publishes → execution sends it → teardown reads what execution got."""
    return textwrap.dedent(
        f"""
        kind: test
        syntax: v1-alpha
        namespace: {_TCK_ID}
        id: wiring
        metadata:
          name: Wiring
          version: v1.0.0
          description: One value, carried from env through all three phases.
        setup:
          - id: reserve
            uses: http/http_request
            name: Reserve a slot for this part
            with:
              method: POST
              url: {base_url}/reservations
              body:
                part: "${{{{ env.part_number.value }}}}"
            returns:
              body.ticket:
                type: string
            validate:
              - uses: validate/assert
                with: {{ input: body.ticket, operator: not_null }}
        execution:
          - id: claim
            uses: http/http_request
            name: Claim the reservation setup made
            with:
              method: GET
              url: {base_url}/reservations/claim
              headers:
                X-Ticket: "${{{{ setup.reserve.body.ticket }}}}"
            returns:
              body.state:
                type: string
              status_code:
                type: integer
            validate:
              - uses: validate/assert
                with: {{ input: status_code, operator: equals, value: 200 }}
              - uses: validate/assert
                with: {{ input: body.state, operator: equals, value: CLAIMED }}
        teardown:
          - id: release
            uses: http/http_request
            name: Release it again, naming what execution saw
            with:
              method: DELETE
              url: {base_url}/reservations/release
              headers:
                X-Ticket: "${{{{ setup.reserve.body.ticket }}}}"
                X-State: "${{{{ execution.claim.body.state }}}}"
        """
    ).lstrip()


def _checks_test(base_url: str) -> str:
    """One step, several assertions, one of which is soft."""
    return textwrap.dedent(
        f"""
        kind: test
        syntax: v1-alpha
        namespace: {_TCK_ID}
        id: checks
        metadata:
          name: Checks
          version: v1.0.0
          description: Every declared check is evaluated and recorded.
        execution:
          - id: read
            uses: http/http_request
            name: Read the part document
            with:
              method: GET
              url: {base_url}/parts/PART-4711
            returns:
              body:
                type: object
              status_code:
                type: integer
            validate:
              - uses: validate/assert
                with: {{ input: status_code, operator: equals, value: 200 }}
              - uses: validate/field
                with: {{ input: body, path: id, operator: equals, value: PART-4711 }}
              - uses: validate/field
                with: {{ input: body, path: revisions, operator: length_equals, value: 2 }}
              - uses: validate/field
                with:
                  input: body
                  path: nickname
                  operator: not_null
                  severity: SOFT
        """
    ).lstrip()


def _required_test(base_url: str) -> str:
    return textwrap.dedent(
        f"""
        kind: test
        syntax: v1-alpha
        namespace: {_TCK_ID}
        id: required
        metadata:
          name: Required
          version: v1.0.0
          description: Not skippable, so every combination runs it.
        execution:
          - id: ping
            uses: http/http_request
            name: Ping the service
            with:
              method: GET
              url: {base_url}/health
            returns:
              status_code:
                type: integer
            validate:
              - uses: validate/assert
                with: {{ input: status_code, operator: equals, value: 200 }}
        """
    ).lstrip()


@pytest.fixture
def service() -> HttpDouble:
    """The SUT: it issues a ticket, and expects to see it come back."""
    http = HttpDouble()
    http.json_route("POST", "/reservations", {"ticket": "TCK-9001"}, status=201)
    http.json_route("GET", "/reservations/claim", {"state": "CLAIMED"})
    http.json_route("DELETE", "/reservations/release", {"released": True})
    http.json_route(
        "GET", "/parts/PART-4711", {"id": "PART-4711", "revisions": ["a", "b"], "nickname": None}
    )
    http.json_route("GET", "/health", {"ok": True})
    yield http
    http.stop()


@pytest.fixture
def package(tmp_path: Path, service: HttpDouble) -> Path:
    """An authored TCK, compiled the way `testlab compile` compiles one."""
    base_url = service.start()
    source = tmp_path / "src"
    (source / "tests").mkdir(parents=True)
    (source / "index.yaml").write_text(_manifest(), encoding="utf-8")
    (source / "tests" / "wiring.yaml").write_text(_wiring_test(base_url), encoding="utf-8")
    (source / "tests" / "checks.yaml").write_text(_checks_test(base_url), encoding="utf-8")
    (source / "tests" / "required.yaml").write_text(_required_test(base_url), encoding="utf-8")

    from tractusx_testlab.cli.compile import compile as compile_command

    compile_command(
        script=source / "index.yaml",
        compiler_keys=None,
        player_pub=None,
        output=tmp_path / "dist",
        version=None,
        plain=False,
    )
    return tmp_path / "dist" / f"{_TCK_ID}.tck"


async def _run(package: Path, tmp_path: Path, **runtime_vars: object):
    player = TestlabPlayer(config=TestlabConfig(logs_dir=tmp_path / "logs"))
    return await player.run_tck(Loader().load(package), runtime_vars=runtime_vars or None)


class TestTheAuthoredTckCompiles:
    def test_the_manifest_validates(self, tmp_path: Path, package: Path) -> None:
        result = Compiler().validate(tmp_path / "src" / "index.yaml")
        assert result.valid, [issue.message for issue in result.issues]

    def test_one_sealed_package_comes_out(self, package: Path) -> None:
        assert package.exists()
        Loader().load(package)  # verifies the digest; raises if it does not match

    def test_the_package_carries_every_test_the_manifest_declared(self, package: Path) -> None:
        report = _inspection.build_inspection_result(Loader().load(package))
        assert {script.test_id for script in report.scripts} == {
            "wiring.yaml",
            "checks.yaml",
            "required.yaml",
        }

    def test_the_package_counts_the_steps_of_every_phase(self, package: Path) -> None:
        """3 (wiring) + 1 (checks) + 1 (required); wiring's setup and teardown count."""
        report = _inspection.build_inspection_result(Loader().load(package))
        assert report.total_steps == 5


@_ASYNC
class TestRuntimeWiring:
    """A value published by one step reaches the next — checked on the wire."""

    async def test_the_run_passes(self, package: Path, tmp_path: Path) -> None:
        result = await _run(package, tmp_path)
        assert result.status == ScriptStatus.COMPLETED, [
            step.error for script in result.scripts for step in script.execution if step.error
        ]

    async def test_the_setup_ticket_reaches_the_execution_request(
        self, package: Path, tmp_path: Path, service: HttpDouble
    ) -> None:
        await _run(package, tmp_path)
        claim = next(r for r in service.received if r.path == "/reservations/claim")
        assert claim.headers.get("X-Ticket") == "TCK-9001"

    async def test_the_execution_state_reaches_the_teardown_request(
        self, package: Path, tmp_path: Path, service: HttpDouble
    ) -> None:
        """Across two phase boundaries, and out of a response body.

        Teardown reads ``execution.claim.body.state``, which existed only
        inside the JSON the SUT answered the *execution* step with.
        """
        await _run(package, tmp_path)
        release = next(r for r in service.received if r.path == "/reservations/release")
        assert release.headers.get("X-State") == "CLAIMED"
        assert release.headers.get("X-Ticket") == "TCK-9001"

    async def test_an_env_variable_reaches_the_first_request(
        self, package: Path, tmp_path: Path, service: HttpDouble
    ) -> None:
        await _run(package, tmp_path)
        reserve = next(r for r in service.received if r.path == "/reservations")
        assert reserve.body == {"part": "PART-4711"}


@_ASYNC
class TestAssertionsAreRecorded:
    async def test_every_declared_check_was_evaluated(self, package: Path, tmp_path: Path) -> None:
        result = await _run(package, tmp_path)
        checks = next(s for s in result.scripts if s.script_name == "Checks")
        assert checks.assertion_summary.declared == checks.assertion_summary.total
        assert checks.assertion_summary.total == 4

    async def test_they_are_recorded_against_the_step_that_declared_them(
        self, package: Path, tmp_path: Path
    ) -> None:
        result = await _run(package, tmp_path)
        checks = next(s for s in result.scripts if s.script_name == "Checks")
        read = next(step for step in checks.execution if "[read]" in step.step_name)
        assert len(read.assertions) == 4

    async def test_a_soft_failure_does_not_fail_the_step(
        self, package: Path, tmp_path: Path
    ) -> None:
        """``nickname`` is null in the document; the check is SOFT, so it is
        reported as failed and the step still passes."""
        result = await _run(package, tmp_path)
        checks = next(s for s in result.scripts if s.script_name == "Checks")
        read = next(step for step in checks.execution if "[read]" in step.step_name)
        assert read.status == StepStatus.PASSED
        assert checks.assertion_summary.failed_soft == 1
        assert checks.assertion_summary.failed_hard == 0

    async def test_the_wire_is_recorded_with_the_step(self, package: Path, tmp_path: Path) -> None:
        """The trace carries the request and the response, not just the verdict."""
        result = await _run(package, tmp_path)
        checks = next(s for s in result.scripts if s.script_name == "Checks")
        read = next(step for step in checks.execution if "[read]" in step.step_name)
        assert read.request is not None and read.request.method == "GET"
        assert read.response is not None and read.response.status_code == 200
        assert read.response.body["id"] == "PART-4711"


@_ASYNC
class TestCombinations:
    """One compiled package, several selections."""

    async def test_the_full_suite_runs_every_test(self, package: Path, tmp_path: Path) -> None:
        result = await _run(package, tmp_path)
        assert len(result.scripts) == 3
        assert all(s.status == ScriptStatus.COMPLETED for s in result.scripts)

    async def test_a_selection_runs_only_what_was_asked_for(
        self, package: Path, tmp_path: Path
    ) -> None:
        result = await _run(package, tmp_path, skip_tests=["checks.yaml"])
        by_name = {s.script_name: s.status for s in result.scripts}
        assert by_name["Checks"] == ScriptStatus.SKIPPED
        assert by_name["Wiring"] == ScriptStatus.COMPLETED

    async def test_skipping_does_not_fail_the_run(self, package: Path, tmp_path: Path) -> None:
        """An omitted test is an operator's choice, not a defect."""
        result = await _run(package, tmp_path, skip_tests=["checks.yaml", "wiring.yaml"])
        assert result.status == ScriptStatus.COMPLETED

    async def test_a_selection_does_not_reach_the_skipped_tests_service(
        self, package: Path, tmp_path: Path, service: HttpDouble
    ) -> None:
        await _run(package, tmp_path, skip_tests=["checks.yaml"])
        assert not [r for r in service.received if r.path == "/parts/PART-4711"]

    async def test_an_unknown_test_id_is_refused(self, package: Path, tmp_path: Path) -> None:
        """A mistyped id must stop the run, not quietly select nothing."""
        with pytest.raises(SkipNotAllowedError, match="no-such-test"):
            await _run(package, tmp_path, skip_tests=["no-such-test.yaml"])

    async def test_a_test_the_manifest_requires_cannot_be_omitted(
        self, package: Path, tmp_path: Path
    ) -> None:
        """This is what makes a certification TCK a certification TCK."""
        with pytest.raises(SkipNotAllowedError, match="required.yaml"):
            await _run(package, tmp_path, skip_tests=["required.yaml"])

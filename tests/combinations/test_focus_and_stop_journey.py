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

"""``on_failure: stop`` and a focus run, authored, compiled, loaded and run as an operator's TCK is.

``gate.yaml`` is marked ``on_failure: stop`` and its service answers 500, so
it fails; ``after.yaml`` would pass. A plain run stops after the gate; a focus
run on ``after.yaml`` alone runs only that test.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from combinations.http_double import HttpDouble
from tractusx_testlab.authoring import _inspection
from tractusx_testlab.compiler.ir.builder import build_ir
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import TestStatus, UnknownFocusTestError
from tractusx_testlab.player import TestlabPlayer
from tractusx_testlab.player.loading.loader import Loader

_TCK_ID = "focus-tck"

_MANIFEST = f"""
kind: tck
syntax: v1-alpha
id: {_TCK_ID}
metadata:
  name: Focus TCK
  version: v1.0.0
  description: A gate that stops the run, and a test after it.
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
tests:
  - id: gate.yaml
    name: The gate
    on_failure: stop
  - id: after.yaml
    name: After the gate
"""


def _test(test_id: str, path: str, base_url: str) -> str:
    return textwrap.dedent(
        f"""
        kind: test
        syntax: v1-alpha
        namespace: {_TCK_ID}
        id: {test_id}
        metadata:
          name: {test_id}
          version: v1.0.0
          description: Calls {path}.
        execution:
          - id: call
            uses: http/http_request
            name: Call {path}
            with:
              method: GET
              url: {base_url}{path}
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
    http = HttpDouble()
    http.json_route("GET", "/gate", {"ok": False}, status=500)
    http.json_route("GET", "/after", {"ok": True})
    yield http
    http.stop()


@pytest.fixture
def package(tmp_path: Path, service: HttpDouble) -> Path:
    base_url = service.start()
    source = tmp_path / "src"
    (source / "tests").mkdir(parents=True)
    (source / "index.yaml").write_text(_MANIFEST.lstrip(), encoding="utf-8")
    for test_id in ("gate", "after"):
        body = _test(test_id, f"/{test_id}", base_url)
        (source / "tests" / f"{test_id}.yaml").write_text(body, encoding="utf-8")

    from tractusx_testlab.cli.compile import compile as compile_command

    compile_command(
        manifest=source / "index.yaml",
        compiler_keys=None,
        player_pub=None,
        output=tmp_path / "dist",
        version=None,
        plain=False,
    )
    return tmp_path / "dist" / f"{_TCK_ID}.tck"


@pytest.fixture
def player(tmp_path: Path) -> tuple[TestlabPlayer, list[dict]]:
    player = TestlabPlayer(config=TestlabConfig(logs_dir=tmp_path / "logs"))
    envelopes: list[dict] = []
    player.monitor.add_trace_callback(
        lambda _event, _payload, envelope: envelopes.append(envelope) if envelope else None
    )
    return player, envelopes


def _skipped_events(envelopes: list[dict]) -> list[dict]:
    return [e["data"] for e in envelopes if e["type"] == "tck.test.skipped"]


class TestThePackage:
    def test_the_compiled_package_carries_on_failure(self, package: Path) -> None:
        manifest, _ = build_ir(package.parent.parent / "src" / "index.yaml")
        assert [entry.get("on_failure") for entry in manifest["tests"]] == ["stop", None]

    def test_the_loaded_tck_and_its_inspection_say_so(self, package: Path) -> None:
        tck = Loader().load(package)
        assert [test.on_failure for test in tck.tests] == ["stop", "continue"]
        report = _inspection.build_inspection_result(tck)
        assert [test.on_failure for test in report.tests] == ["stop", "continue"]


@pytest.mark.asyncio
class TestARun:
    async def test_a_failed_gate_stops_the_run(
        self, package: Path, player, service: HttpDouble
    ) -> None:
        player, envelopes = player
        result = await player.run_tck(Loader().load(package))

        assert [test.status for test in result.tests] == [TestStatus.FAILED, TestStatus.SKIPPED]
        assert result.status == TestStatus.FAILED
        assert not service.calls_to("GET", "/after")
        [skipped] = _skipped_events(envelopes)
        assert skipped["test_id"] == "after"
        assert skipped["reason"] == "stopped: gate.yaml failed and is marked on_failure: stop"

    async def test_a_focus_run_runs_only_its_selection(
        self, package: Path, player, service: HttpDouble
    ) -> None:
        player, envelopes = player
        tck = Loader().load(package)
        result = await player.run_tck(tck, runtime_vars={"only_tests": ["after.yaml"]})

        assert [test.status for test in result.tests] == [TestStatus.SKIPPED, TestStatus.COMPLETED]
        assert result.status == TestStatus.COMPLETED
        assert (result.focus, result.only_tests) == (True, ["after.yaml"])
        assert not service.calls_to("GET", "/gate")
        [skipped] = _skipped_events(envelopes)
        assert skipped["test_id"] == "gate"
        assert skipped["reason"] == "not selected for this focus run"

    async def test_an_unknown_focus_id_runs_nothing(
        self, package: Path, player, service: HttpDouble
    ) -> None:
        player, _ = player
        with pytest.raises(UnknownFocusTestError, match="nope.yaml"):
            await player.run_tck(Loader().load(package), runtime_vars={"only_tests": "nope.yaml"})
        assert not service.received

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


"""A session: the tests that run on their own, then one test run when asked, again.

Authored, compiled and loaded the way an operator's TCK is. ``push.yaml`` is
marked ``async: true`` (labs): a session leaves it until it is asked for, and
runs it as often as it is asked; a plain run runs it like any other test.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from combinations.http_double import HttpDouble
from tractusx_testlab.authoring import _inspection
from tractusx_testlab.compiler.compiler import Compiler
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.models import TestStatus
from tractusx_testlab.player import SessionClosedError, TestlabPlayer
from tractusx_testlab.player.loading.loader import Loader

_TCK_ID = "session-tck"


def _manifest(extensions: str = "[labs]") -> str:
    return textwrap.dedent(
        f"""
        kind: tck
        syntax: v1-alpha
        id: {_TCK_ID}
        metadata:
          name: Session TCK
          version: v1.0.0
          description: One test on its own, one on demand.
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
        extensions: {extensions}
        tests:
          - id: push.yaml
            name: Pushed when asked
            async: true
          - id: ping.yaml
            name: Runs on its own
        """
    ).lstrip()


def _test(test_id: str, path: str, base_url: str) -> str:
    """setup mints a ticket, execution sends it: a re-run has to mint its own."""
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
        setup:
          - id: mint
            uses: http/http_request
            name: Mint a ticket
            with:
              method: POST
              url: {base_url}/tickets
            returns:
              body.ticket:
                type: string
        execution:
          - id: call
            uses: http/http_request
            name: Call {path}
            with:
              method: POST
              url: {base_url}{path}
              headers:
                X-Ticket: "${{{{ setup.mint.body.ticket }}}}"
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
    http.json_route("POST", "/tickets", {"ticket": "T-1"})
    http.json_route("POST", "/push", {"ok": True})
    http.json_route("POST", "/ping", {"ok": True})
    yield http
    http.stop()


def _author(tmp_path: Path, base_url: str, extensions: str = "[labs]") -> Path:
    source = tmp_path / "src"
    (source / "tests").mkdir(parents=True)
    (source / "index.yaml").write_text(_manifest(extensions), encoding="utf-8")
    (source / "tests" / "push.yaml").write_text(_test("push", "/push", base_url), encoding="utf-8")
    (source / "tests" / "ping.yaml").write_text(_test("ping", "/ping", base_url), encoding="utf-8")
    return source / "index.yaml"


@pytest.fixture
def package(tmp_path: Path, service: HttpDouble) -> Path:
    manifest = _author(tmp_path, service.start())

    from tractusx_testlab.cli.compile import compile as compile_command

    compile_command(
        manifest=manifest,
        compiler_keys=None,
        player_pub=None,
        output=tmp_path / "dist",
        version=None,
        plain=False,
    )
    return tmp_path / "dist" / f"{_TCK_ID}.tck"


@pytest.fixture
def player(tmp_path: Path) -> tuple[TestlabPlayer, list[tuple[str, dict]]]:
    player = TestlabPlayer(config=TestlabConfig(logs_dir=tmp_path / "logs"))
    events: list[tuple[str, dict]] = []
    player.monitor.add_callback(lambda event, payload: events.append((event, payload)))
    return player, events


def _of(events: list[tuple[str, dict]], name: str) -> list[dict]:
    return [payload for event, payload in events if event == name]


class TestTheManifest:
    def test_async_needs_the_labs_extension(self, tmp_path: Path) -> None:
        manifest = _author(tmp_path, "http://localhost:1", extensions="[]")
        result = Compiler().validate(manifest)
        assert any(
            "'async:' on the tests entry 'push.yaml'" in issue.message and "labs" in issue.message
            for issue in result.issues
            if issue.level == "error"
        ), [issue.message for issue in result.issues]

    def test_with_labs_it_compiles_and_the_package_says_so(self, package: Path) -> None:
        tck = Loader().load(package)
        assert [test.on_demand for test in tck.tests] == [True, False]
        report = _inspection.build_inspection_result(tck)
        assert [test.on_demand for test in report.tests] == [True, False]


@pytest.mark.asyncio
class TestASession:
    async def test_only_the_scheduled_tests_run_and_the_others_wait(
        self, package: Path, player, service: HttpDouble
    ) -> None:
        player, events = player
        session = await player.open_session(Loader().load(package))
        try:
            results = await session.run_scheduled()

            assert [result.test_id for result in results] == ["ping"]
            assert not service.calls_to("POST", "/push")
            assert _of(events, "test.awaiting") == [
                {"kind": "test_awaiting", "job_id": session.job_id, "test_id": "push", "index": 0}
            ]
        finally:
            await session.close()

    async def test_a_test_runs_when_asked_and_again(
        self, package: Path, player, service: HttpDouble
    ) -> None:
        player, events = player
        session = await player.open_session(Loader().load(package))
        await session.run_scheduled()

        first = await session.run_test("push.yaml")
        second = await session.run_test("push")  # the test's own id works too

        assert first.status == second.status == TestStatus.COMPLETED
        assert len(service.calls_to("POST", "/push")) == 2
        assert session.attempts("push.yaml") == 2
        started = [e["attempt"] for e in _of(events, "test.started") if e["test_id"] == "push"]
        assert started == [1, 2]

        result = await session.close()
        assert [test.test_id for test in result.tests] == ["push", "ping"]
        assert result.status == TestStatus.COMPLETED

    async def test_the_verdict_counts_the_latest_attempt(
        self, package: Path, player, service: HttpDouble
    ) -> None:
        player, _ = player
        service.json_route("POST", "/push", {"ok": False}, status=500)
        session = await player.open_session(Loader().load(package))
        await session.run_scheduled()
        assert (await session.run_test("push.yaml")).status == TestStatus.FAILED

        service.json_route("POST", "/push", {"ok": True})
        assert (await session.run_test("push.yaml")).status == TestStatus.COMPLETED

        assert (await session.close()).status == TestStatus.COMPLETED

    async def test_a_test_never_asked_for_is_reported_skipped(self, package: Path, player) -> None:
        player, events = player
        session = await player.open_session(Loader().load(package))
        await session.run_scheduled()

        result = await session.close()

        assert {test.test_id: test.status for test in result.tests} == {
            "push": TestStatus.SKIPPED,
            "ping": TestStatus.COMPLETED,
        }
        assert result.status == TestStatus.COMPLETED
        assert len(_of(events, "job.completed")) == 1

    async def test_a_closed_session_runs_nothing_and_closes_once(
        self, package: Path, player
    ) -> None:
        player, events = player
        session = await player.open_session(Loader().load(package))
        first = await session.close()

        with pytest.raises(SessionClosedError):
            await session.run_test("push.yaml")
        assert await session.close() is first
        assert len(_of(events, "job.completed")) == 1

    async def test_a_close_a_host_interrupts_still_releases_the_run(
        self, package: Path, player
    ) -> None:
        """An engine abandoning a cancelled run raises from its event callback."""
        from tractusx_testlab.logging import transcript

        class Abandoned(Exception):
            pass

        player, _ = player
        session = await player.open_session(Loader().load(package))

        def _abandon(event: str, _payload: dict) -> None:
            if event == "test.started":
                raise Abandoned

        player.monitor.add_callback(_abandon)
        with pytest.raises(Abandoned):
            await session.close()

        assert transcript._active is None  # the transcript's tee is gone
        with pytest.raises(SessionClosedError):
            await session.close()

    async def test_an_unknown_test_is_refused(self, package: Path, player) -> None:
        player, _ = player
        session = await player.open_session(Loader().load(package))
        try:
            with pytest.raises(KeyError, match="nope"):
                await session.run_test("nope.yaml")
        finally:
            await session.close()

    async def test_a_rerun_forgets_what_the_previous_attempt_published(
        self, package: Path, player
    ) -> None:
        """A step that fails before it publishes must not leave the old value behind.

        The value stands in for one such a step published on the first attempt:
        a step that raises publishes nothing, so only forgetting clears it.
        """
        player, _ = player
        session = await player.open_session(Loader().load(package))
        await session.run_test("push.yaml")
        context = session._context
        context.set_variable("setup.mint.stale", "from attempt 1")
        context.set_variable("setup.other.kept", "not this test's")

        await session.run_test("push.yaml")

        assert not context.has_variable("setup.mint.stale")
        assert context.get_variable("setup.mint.body.ticket") == "T-1"
        assert context.get_variable("setup.other.kept") == "not this test's"
        await session.close()


@pytest.mark.asyncio
async def test_a_plain_run_runs_the_async_test_in_order(
    package: Path, player, service: HttpDouble
) -> None:
    player, events = player
    result = await player.run_tck(Loader().load(package))

    assert [test.test_id for test in result.tests] == ["push", "ping"]
    assert len(service.calls_to("POST", "/push")) == 1
    assert not _of(events, "test.awaiting")

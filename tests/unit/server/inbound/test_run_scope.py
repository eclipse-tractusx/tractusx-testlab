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

"""A run's address on a shared mock server, and how a call is pinned on a run.

The pure half of keeping runs apart: how a path is put under a run's address
and taken out again, which root a run publishes, and — for a call on a bare
path — which run it can be told to be for, if any.
"""

from __future__ import annotations

import asyncio

import pytest

from tractusx_testlab.server.inbound.run_scope import (
    acting_for,
    current_run,
    declared,
    pick,
    run_root,
    scoped,
    split,
)

_PATH = "/companycertificate/status"


def _never(_key_path: str) -> bool:
    return False


class TestTheRunsAddress:
    def test_a_path_is_kept_under_the_runs_segment(self) -> None:
        assert scoped("run-a", _PATH) == f"/runs/run-a{_PATH}"

    def test_no_run_keeps_the_path_as_it_is(self) -> None:
        assert scoped(None, _PATH) == _PATH
        assert scoped("", _PATH) == _PATH

    def test_scoping_twice_changes_nothing(self) -> None:
        once = scoped("run-a", _PATH)

        assert scoped("run-a", once) == once

    def test_split_gives_back_the_run_and_the_path_the_test_wrote(self) -> None:
        assert split(scoped("run-a", _PATH)) == ("run-a", _PATH)
        assert declared(scoped("run-a", _PATH)) == _PATH

    @pytest.mark.parametrize("path", [_PATH, "/runs", "/runs/", "/runs/run-a", "/running/x"])
    def test_a_path_outside_any_run_is_its_own(self, path: str) -> None:
        assert split(path) == (None, path)

    def test_the_root_of_a_run_is_scoped_unless_it_names_the_run(self) -> None:
        assert run_root("http://localhost:8100", "run-a") == "http://localhost:8100/runs/run-a"
        assert run_root("https://lab.example/", "run-a") == "https://lab.example/runs/run-a"
        # An engine hands each run <origin>/mock/<job id> and forwards that prefix itself.
        engine = "https://engine.example/mock/run-a"
        assert run_root(engine, "run-a") == engine

    def test_a_root_that_names_another_run_is_still_scoped(self) -> None:
        root = run_root("https://engine.example/mock/run-b", "run-a")

        assert root == "https://engine.example/mock/run-b/runs/run-a"


class TestPinningACallOnARun:
    def test_an_exact_registration_is_its_own_answer(self) -> None:
        registered = {_PATH, scoped("run-a", _PATH)}

        assert pick(_PATH, registered, _never) == _PATH
        assert pick(scoped("run-a", _PATH), registered, _never) == scoped("run-a", _PATH)

    def test_the_one_run_that_serves_a_bare_path_is_meant(self) -> None:
        registered = {scoped("run-a", _PATH), scoped("run-b", "/elsewhere")}

        assert pick(_PATH, registered, _never) == scoped("run-a", _PATH)

    def test_the_run_whose_key_the_call_carries_is_meant(self) -> None:
        registered = {scoped("run-a", _PATH), scoped("run-b", _PATH)}

        def carries_b(key_path: str) -> bool:
            return key_path == scoped("run-b", _PATH)

        assert pick(_PATH, registered, carries_b) == scoped("run-b", _PATH)

    def test_a_call_that_names_no_run_is_not_guessed(self) -> None:
        registered = {scoped("run-a", _PATH), scoped("run-b", _PATH)}

        assert pick(_PATH, registered, _never) is None
        assert pick(_PATH, registered, lambda _key_path: True) is None

    def test_an_unopened_path_under_a_known_run_stays_that_runs(self) -> None:
        """It is answered 404 by that run — never handed to another run on the bare path."""
        registered = {scoped("run-a", "/other"), scoped("run-b", _PATH)}

        assert pick(scoped("run-a", _PATH), registered, _never) == scoped("run-a", _PATH)

    def test_a_path_nobody_registered_is_left_as_it_came(self) -> None:
        assert pick(_PATH, {scoped("run-a", "/other")}, _never) == _PATH
        assert pick("/runs/gone/x", set(), _never) == "/runs/gone/x"


class TestTheExecutingRun:
    def test_outside_a_step_there_is_none(self) -> None:
        assert current_run() is None

    def test_inside_the_block_it_is_the_run(self) -> None:
        with acting_for("run-a"):
            assert current_run() == "run-a"
            with acting_for("run-b"):
                assert current_run() == "run-b"
            assert current_run() == "run-a"
        assert current_run() is None

    @pytest.mark.asyncio
    async def test_two_runs_at_once_each_see_their_own(self) -> None:
        async def seen(run: str) -> str | None:
            with acting_for(run):
                await asyncio.sleep(0.01)
                return current_run()

        assert await asyncio.gather(seen("run-a"), seen("run-b")) == ["run-a", "run-b"]

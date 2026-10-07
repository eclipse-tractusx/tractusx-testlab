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

"""What a run leaves on the shared server and on disk once it has ended.

Its mocks, guards and listeners go with it — and only its own: another run
going on in the same process keeps every one of its mocks. Its transcript and
its execution trace stay, readable by the account that ran it alone.
"""

from __future__ import annotations

import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from tractusx_testlab.authoring.parser import YamlParser
from tractusx_testlab.authoring.test import Tck
from tractusx_testlab.config.settings import TestlabConfig
from tractusx_testlab.player.execution.player import TestlabPlayer
from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.server.inbound.run_scope import scoped
from tractusx_testlab.server.mock_registry import (
    MockResponse,
    clear_callback_manager,
    clear_mocks,
    get_mock,
    register_mock,
    required_header,
    set_callback_manager,
)


def _empty_tck() -> Tck:
    return Tck.from_single_test(
        YamlParser.parse_test_from_dict(
            {
                "syntax": "v1-alpha",
                "kind": "test",
                "id": "empty",
                "namespace": "testlab.test",
                "metadata": {"name": "empty", "version": "1.0"},
                "execution": [],
            }
        )
    )


@pytest.fixture()
def manager() -> Iterator[CallbackManager]:
    # Registered up front, so the player starts no server of its own.
    manager = CallbackManager()
    set_callback_manager(manager)
    yield manager
    clear_mocks()
    clear_callback_manager()


@pytest.fixture()
def player(tmp_path: Path) -> TestlabPlayer:
    return TestlabPlayer(
        config=TestlabConfig(
            logs_dir=tmp_path / "records" / "logs",
            data_dir=tmp_path / "records" / "data",
            storage_dir=tmp_path / "store",
        )
    )


class TestARunEnding:
    @pytest.mark.asyncio
    async def test_releases_its_mocks_and_no_others(
        self, manager: CallbackManager, player: TestlabPlayer
    ) -> None:
        for run in ("run-a", "run-b"):
            register_mock("/push", "POST", MockResponse(200), required_header=("k", run), run=run)
            manager.register(scoped(run, "/push"), "POST")

        await player.run_tck(_empty_tck(), job_id="run-a")

        assert get_mock("/push", "POST", run="run-a") is None
        assert required_header("/push", "POST", run="run-a") is None
        assert manager.listening() == [(scoped("run-b", "/push"), "POST")]
        assert get_mock("/push", "POST", run="run-b") is not None
        assert required_header("/push", "POST", run="run-b") == ("k", "run-b")

    @pytest.mark.asyncio
    async def test_leaves_records_only_its_account_can_read(
        self, manager: CallbackManager, player: TestlabPlayer, tmp_path: Path
    ) -> None:
        await player.run_tck(_empty_tck(), job_id="run-a")

        records = [path for path in (tmp_path / "records").rglob("*") if path.is_file()]
        directories = [path for path in (tmp_path / "records").rglob("*") if path.is_dir()]
        assert {path.suffix for path in records} == {".log", ".jsonl"}
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in records)
        assert all(stat.S_IMODE(path.stat().st_mode) == 0o700 for path in directories)

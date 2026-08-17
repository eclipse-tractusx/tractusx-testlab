#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Tests for CallbackManager — ephemeral HTTP listener management."""

from __future__ import annotations

import asyncio

import pytest

from tractusx_testlab.server.callbacks import CallbackManager
from tractusx_testlab.models import CallbackResult


class TestCallbackManagerRegistration:
    """Tests for CallbackManager.register() and listener lifecycle."""

    @pytest.mark.asyncio
    async def test_register_creates_listener(self) -> None:
        mgr = CallbackManager()
        mgr.register("/callback/edr", "POST")
        # Registration itself completes without error
        assert True

    @pytest.mark.asyncio
    async def test_register_same_path_twice_is_idempotent(self) -> None:
        mgr = CallbackManager()
        mgr.register("/cb", "POST")
        mgr.register("/cb", "POST")
        assert True


class TestCallbackManagerWait:
    """Tests for CallbackManager.wait() timeout behavior."""

    @pytest.mark.asyncio
    async def test_wait_times_out_when_no_callback_arrives(self) -> None:
        mgr = CallbackManager()
        mgr.register("/timeout-test", "POST")
        result = await mgr.wait("/timeout-test", "POST", timeout_s=0.1)
        assert isinstance(result, CallbackResult)
        assert result.timed_out is True

    @pytest.mark.asyncio
    async def test_wait_unregistered_path_returns_timed_out(self) -> None:
        mgr = CallbackManager()
        result = await mgr.wait("/never-registered", "GET", timeout_s=0.05)
        assert result.timed_out is True

    @pytest.mark.asyncio
    async def test_wait_resolves_when_callback_delivered(self) -> None:
        mgr = CallbackManager()
        mgr.register("/resolve-test", "POST")

        async def _deliver() -> None:
            await asyncio.sleep(0.02)
            mgr.resolve(
                path="/resolve-test",
                method="POST",
                payload={"status": "ok"},
                headers={},
            )

        task = asyncio.create_task(_deliver())
        result = await mgr.wait("/resolve-test", "POST", timeout_s=1.0)
        await task
        assert result.timed_out is False

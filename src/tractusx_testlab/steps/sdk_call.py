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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Calling the synchronous SDK from an async step, without stopping the loop.

``tractusx-sdk`` is synchronous: its adapters use ``requests`` and none of its
service methods is a coroutine. Called directly from ``async def execute`` it
holds the event loop for the whole round trip — and that loop also runs the
in-process callback server, so a catalog query against a slow connector stops
the SUT's callbacks from being answered while it waits.

Converting the engine's own HTTP calls to ``httpx`` fixed the calls we make.
This is the other side: the calls the SDK makes on our behalf, which are the
long ones — catalog, negotiation, transfer, data pull.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


async def run[T](operation: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking SDK *operation* on a worker thread.

    Used for the SDK calls that reach the network. Calls that only build a
    request — assembling a filter expression, preparing headers — are left
    inline: a thread hop costs more than the work, and moving pure computation
    off the loop buys nothing.
    """
    return await asyncio.to_thread(operation, *args, **kwargs)

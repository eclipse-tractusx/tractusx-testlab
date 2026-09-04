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

Long, and until now unbounded. The SDK issues every request through
``requests`` with no timeout, so a connector that accepts the connection and
then never answers holds the call open indefinitely; the SDK's own poll loops
add ``poll_interval`` to their elapsed time only once a call has *returned*, so
their ``max_wait`` never fires on a query that is still hanging. A negotiation
that was not working therefore did not fail — it ran until CI killed the job,
which is no verdict about the SUT at all. Every call made through here now has
a deadline, and reaching it is a failure of that step with the operation and
the seconds waited in the message.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tractusx_testlab.models import StepExecutionError

#: Seconds any single SDK call may take before the step it belongs to fails.
#: Generous on purpose — it is the bound on a call that is *not answering*, not
#: a service-level objective — but finite, which is the whole point. Operations
#: that legitimately take longer because they poll (the DSP flow) pass their own
#: budget to :func:`run_within`.
DEFAULT_SDK_TIMEOUT = 120.0


async def run[T](operation: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking SDK *operation* on a worker thread, bounded by the default.

    Used for the SDK calls that reach the network. Calls that only build a
    request — assembling a filter expression, preparing headers — are left
    inline: a thread hop costs more than the work, and moving pure computation
    off the loop buys nothing.
    """
    return await run_within(DEFAULT_SDK_TIMEOUT, operation, *args, **kwargs)


async def run_within[T](
    timeout: float, operation: Callable[..., T], /, *args: Any, **kwargs: Any
) -> T:
    """Run a blocking SDK *operation*, failing the step after *timeout* seconds.

    For the calls whose own waiting makes the default too tight: a step that
    polls for ``max_wait`` seconds has to be allowed at least that long, and
    says so by passing the budget it computed from its own inputs.

    A worker thread cannot be cancelled, so the abandoned call keeps whatever
    socket it is stuck on until the connector closes it. That is the cost of
    reporting at all: the alternative is the run waiting on the same socket.

    Raises:
        StepExecutionError: if the call has not returned within *timeout*.
    """
    try:
        return await asyncio.wait_for(asyncio.to_thread(operation, *args, **kwargs), timeout)
    except TimeoutError as exc:
        raise StepExecutionError(
            _name_of(operation),
            f"the connector did not answer within {timeout:g}s — "
            "the call was abandoned so the run could report on it",
        ) from exc


def _name_of(operation: Callable[..., Any]) -> str:
    """What to call the operation in an error message.

    The SDK method's own name, qualified by the service it was reached through,
    so a timeout says which call hung rather than only that one did.
    """
    name = getattr(operation, "__qualname__", None) or getattr(operation, "__name__", "")
    return f"sdk/{name}" if name else "sdk"

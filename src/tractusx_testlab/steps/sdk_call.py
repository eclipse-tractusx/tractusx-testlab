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

"""Calling the synchronous SDK from an async step, and naming what it reports.

``tractusx-sdk`` is synchronous: its adapters use ``requests`` and none of its
service methods is a coroutine. Called directly from ``async def execute`` it
holds the event loop for the whole round trip — and that loop also runs the
in-process callback server, so a catalog query against a slow connector stops
the SUT's callbacks from being answered while it waits.

Converting the engine's own HTTP calls to ``httpx`` fixed the calls we make.
This is the other side: the calls the SDK makes on our behalf, which are the
long ones — catalog, negotiation, transfer, data pull.

It is also the one place every SDK call crosses, which makes it the place its
failure is named. The SDK reports a service that did not do its part the same
way every time: a ``RuntimeError`` carrying the service's own sentence. The
runner classifies an exception it did not raise, and treats anything that is
not a ``TestLabError`` as an engine fault — so *the provider did not share any
matching asset* reached the report as **TestLab reported this as its own
fault**, sending the reader to file a bug about a catalog the SUT never
published. That channel becomes a
:class:`~tractusx_testlab.models.BoundServiceError` here: not a verdict about
the SUT, not a defect in TestLab, but a deployment that did not hold up its
end. A call bound to a connector service is the case of it with two ends, and
is named :class:`~tractusx_testlab.models.ConnectorError`, because the SDK
reports the failure of the pair and which end it was is open.

Only that channel is translated. A ``TypeError`` from calling the SDK wrongly
is still ours, and still reaches the runner as the engine fault it is. And one
connector failure is a verdict after all — a catalog whose offers were all
refused — which :mod:`~tractusx_testlab.steps.connector.policy_mismatch`
replaces with the comparison behind it, on top of what is named here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from tractusx_sdk.dataspace.services.connector import (
    BaseConnectorConsumerService,
    BaseConnectorProviderService,
)

from tractusx_testlab.models import BoundServiceError, ConnectorError

#: The services whose failure has two ends. A method bound to one of these ran
#: a dataspace exchange, and the SDK reports the exchange, not a side.
_CONNECTOR_SERVICES = (BaseConnectorConsumerService, BaseConnectorProviderService)


async def run[T](operation: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking SDK *operation* on a worker thread, and name its failure.

    Used for the SDK calls that reach the network. Calls that only build a
    request — assembling a filter expression, preparing headers — are left
    inline: a thread hop costs more than the work, and moving pure computation
    off the loop buys nothing.

    A ``RuntimeError`` the operation reports is raised as the failure of the
    service it is bound to — ``ConnectorError`` for a connector service,
    ``BoundServiceError`` for any other — with the SDK's own message kept as
    the cause. Everything else passes through unchanged.
    """
    try:
        return await asyncio.to_thread(operation, *args, **kwargs)
    except RuntimeError as exc:
        raise _failure_of(operation)(str(exc)) from exc


def _failure_of(operation: Callable[..., Any]) -> type[BoundServiceError]:
    """The error class that says which service *operation* belongs to."""
    service = getattr(operation, "__self__", None)
    if isinstance(service, _CONNECTOR_SERVICES):
        return ConnectorError
    return BoundServiceError

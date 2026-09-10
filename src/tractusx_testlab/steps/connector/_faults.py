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


"""Naming what came back when a connector exchange did not go through.

The dataspace half of :mod:`~tractusx_testlab.steps.faults`: the same SDK
failure channel, named as the one infrastructure failure that has two ends. A
catalog carrying no matching asset, a negotiation that never finalised — the
fault may be the SUT's connector, the one TestLab drives, or the network
between them, and none of the three is *TestLab reported this as its own
fault*, which is what the report used to say.

One thing happens here that does not happen for any other service: a catalog
whose offers were all refused is a verdict about the provider, and
:mod:`~tractusx_testlab.steps.connector.policy_mismatch` replaces the SDK's flat
sentence with the comparison behind it (``POLICY_MISMATCH``, ``sut``).
Everything else on that channel is the exchange itself failing
(``CONNECTOR_ERROR``, ``connector``).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from tractusx_testlab.models import ConnectorError
from tractusx_testlab.steps import faults, sdk_call
from tractusx_testlab.steps.connector import policy_mismatch

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


@contextmanager
def connector_exchange(counter_party_address: str | None = None) -> Iterator[None]:
    """Run SDK connector calls, and name the failure they report.

    *counter_party_address* is the party the exchange is with. Naming it turns
    on the policy explanation, which only means something for a call that ran a
    catalog match; a call that did not — reading an EDR, polling a negotiation,
    discovering a connector — leaves it out and gets the connector
    classification alone.
    """
    with faults.named_as(ConnectorError):
        if counter_party_address is None:
            yield
        else:
            with policy_mismatch.explained(counter_party_address):
                yield


async def call[T](operation: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """:func:`~tractusx_testlab.steps.sdk_call.run`, with the failure named.

    The one-call form of :func:`connector_exchange`, for the steps that make a
    single SDK call and run no catalog match. A step whose call *does* match
    policies takes the context manager instead, and gets the comparison too.
    """
    with connector_exchange():
        return await sdk_call.run(operation, *args, **kwargs)

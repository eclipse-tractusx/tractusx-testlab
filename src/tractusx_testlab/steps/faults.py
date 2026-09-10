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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Naming a service that did not do its part, so the run does not blame itself.

The SDK reports every one of them the same way: a ``RuntimeError`` carrying the
service's own sentence. The runner has to classify an exception it did not
raise, and treats anything that is not a ``TestLabError`` as an engine fault —
so *the provider did not share any matching asset* reached the report as
**TestLab reported this as its own fault**, sending the reader to file a bug
about a catalog the SUT never published.

That channel is the only thing translated here, and it becomes an
:class:`~tractusx_testlab.models.BoundServiceError`: not a verdict about the
SUT, not a defect in TestLab, but a deployment that did not hold up its end.
A ``TypeError`` from calling the SDK wrongly is still ours, and still reaches
the runner as the engine fault it is.

The dataspace exchange has its own subclass and its own module — see
:mod:`~tractusx_testlab.steps.connector._faults`, which adds the policy
comparison a refused catalog deserves.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from tractusx_testlab.models import BoundServiceError
from tractusx_testlab.steps import sdk_call

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


@contextmanager
def named_as(failure: type[BoundServiceError] = BoundServiceError) -> Iterator[None]:
    """Run SDK calls, and raise *failure* for the channel they report through.

    *failure* is the subclass that says which service this was, when the caller
    knows one — ``ConnectorError`` for a DSP exchange. The default is the plain
    infrastructure failure, which says the deployment rather than which part.
    """
    try:
        yield
    except RuntimeError as exc:
        raise failure(str(exc)) from exc


async def call[T](operation: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """:func:`~tractusx_testlab.steps.sdk_call.run`, with the failure named.

    The one-call form of :func:`named_as`, for the steps that make a single SDK
    call — reading a shell descriptor, registering a submodel, asking the
    registry for a twin.
    """
    with named_as():
        return await sdk_call.run(operation, *args, **kwargs)

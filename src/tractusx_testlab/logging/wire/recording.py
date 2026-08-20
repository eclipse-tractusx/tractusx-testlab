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

"""Recording what actually went over the wire, for the whole of a step.

A conformance verdict is a claim about what the SUT answered, so the answer is
the evidence. A step reports an exchange only if it built one by hand on its way
to returning a value — which leaves the failing case, the one worth debugging,
reporting nothing at all: a step that raised never reached the line that would
have described its request.

Two transports carry a run's traffic, and one mechanism records both — the
SDK's tracer:

* ``requests`` — the calls ``tractusx-sdk`` makes on the engine's behalf, which
  are the long ones (catalog, negotiation, transfer, data pull) and the ones the
  engine never sees. The SDK records them itself, at the two places where it
  talks to an external service, into whichever tracer is active. Nothing has to
  be wired into the services or the adapters for that, and nothing has to be
  patched: the engine wrapped ``requests.adapters.HTTPAdapter.send`` because
  there was no way in, and there is one now.
* ``httpx`` — the engine's own calls, made through
  :mod:`tractusx_testlab.steps.http_client`, which records them through the same
  ``trace_call`` the SDK instruments itself with, so both transports land in one
  ordered list under one redaction and truncation policy.

A step reports the calls it made itself. The tracer is activated per step as a
named *operation* and every entry is stamped with the innermost one, so a flow
step that runs nested steps keeps what it sent and the nested steps keep theirs
— rather than the parent claiming its children's traffic twice over.

Activation is by :class:`contextvars.ContextVar`, so a step running on the event
loop and the SDK call it dispatched to a worker thread record into the same
operation — ``asyncio.to_thread`` copies the context (see
:mod:`tractusx_testlab.steps.sdk_call`).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any

from tractusx_sdk.dataspace.tools import Tracer

from tractusx_testlab.logging.wire.records import SECRET_HEADERS
from tractusx_testlab.models.runtime.results import HttpExchange, HttpRequest, HttpResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tractusx_sdk.dataspace.tools import TraceEntry, TraceOperation

#: Most calls kept per step. A step that polls can legitimately make hundreds,
#: and a step's tracer also collects what the steps nested inside it sent (the
#: read filters those back out), so the bound is set well above any real step
#: rather than at the number a step is expected to make. Past it the oldest
#: calls are dropped, which for a poll loop keeps the end — where the failure is.
_MAX_CALLS = 1000

#: Longest body kept per exchange. A data-plane pull can answer megabytes; the
#: trace is for debugging the conversation, not for archiving the payload. The
#: tracer trims the content rather than the serialized form, so a clipped JSON
#: body is still JSON, with a marker where the rest was.
_MAX_BODY_CHARS = 20_000

#: What a call the engine made itself is attributed to. SDK calls carry the SDK
#: method that performed them, so the two are told apart in the trace by the
#: same field rather than by the reader guessing from the URL.
ENGINE_CONTEXT = "testlab/http_client"


#: Who to hand a finished call to, per step being recorded. Keyed by operation
#: rather than held on the tracer because the SDK completes an entry on the
#: *outermost* active tracer: a nested step's calls are finished by its parent's
#: tracer, and the entry itself is what says whose call it was.
_reporters: dict[str, Callable[[HttpExchange], None]] = {}
_reporters_lock = threading.Lock()


class _LiveTracer(Tracer):
    """A tracer that hands each call over the moment its answer is in.

    A step is not one call, and the long ones are long because they are many: a
    DSP pull is a catalog query, a negotiation and a poll loop that can run for a
    minute. Reporting the conversation when the step ends leaves whoever is
    watching a spinner and nothing else for that minute, so each call is reported
    as it completes — from whichever thread made it, which is why the reporter it
    reaches has to be the one that can be called from anywhere.
    """

    def complete_entry(
        self,
        entry: TraceEntry,
        response: Any = None,
        error: BaseException | None = None,
        duration_ms: float | None = None,
    ) -> TraceEntry:
        completed = super().complete_entry(
            entry, response=response, error=error, duration_ms=duration_ms
        )
        with _reporters_lock:
            report = _reporters.get(completed.operation_id or "")
        if report is not None:
            report(_to_exchange(completed))
        return completed


class ExchangeRecorder:
    """The calls one step made, as the tracer recorded them.

    A view over the trace rather than a second copy of it: the entries live in
    the tracer's single ordered list, and reading them here selects the ones
    stamped with this step's operation.
    """

    __slots__ = ("_operation", "_tracer")

    def __init__(self, tracer: Tracer, operation: TraceOperation) -> None:
        self._tracer = tracer
        self._operation = operation

    @property
    def exchanges(self) -> list[HttpExchange]:
        """Every call the step made itself, in the order it made them."""
        return [
            _to_exchange(entry) for entry in self._tracer.filter(operation_id=self._operation.id)
        ]


@contextmanager
def recording(
    name: str | None = None,
    on_call: Callable[[HttpExchange], None] | None = None,
) -> Iterator[ExchangeRecorder]:
    """Record every HTTP call made in this block, whichever transport made it.

    *name* is the step being run. It names the operation the calls are grouped
    under, which is what a trace read straight from the tracer is navigated by.

    *on_call* is handed each call as it finishes, for a run that reports the
    conversation while it happens rather than once it is over. It is called from
    the thread that made the call — the event loop for the engine's own calls, a
    worker thread for the SDK's — so what it does has to be safe from both.
    """
    tracer = _LiveTracer(
        name=name,
        max_entries=_MAX_CALLS,
        max_body_chars=_MAX_BODY_CHARS,
        redacted_headers=set(SECRET_HEADERS),
    )
    with tracer.activate(name) as operation:
        if on_call is not None:
            with _reporters_lock:
                _reporters[operation.id] = on_call
        try:
            yield ExchangeRecorder(tracer, operation)
        finally:
            with _reporters_lock:
                _reporters.pop(operation.id, None)


def attach_to(result: Any, recorder: ExchangeRecorder) -> None:
    """Give a :class:`StepResult` everything the step sent.

    A step that built its own ``request`` / ``response`` keeps them: it chose
    which of its calls the script is really about. A step that raised chose
    nothing, so the last exchange stands in — and for a failure that is the call
    that failed, which is the whole point of recording at all.
    """
    exchanges = recorder.exchanges
    if not exchanges:
        return
    result.exchanges = exchanges
    if result.request is None and result.response is None:
        last = exchanges[-1]
        result.request = last.request
        result.response = last.response


def _to_exchange(entry: TraceEntry) -> HttpExchange:
    """Turn one trace entry into the exchange a step result reports.

    The tracer has already sanitised what it holds — headers redacted, bodies
    parsed and clipped — so this is a rename, not a second pass. ``duration_ms``
    is taken from the entry rather than from the response: the entry measures
    the call the engine waited on, and a response that never came still has one.
    """
    request = entry.request or {}
    response = entry.response or {}
    status_code = response.get("status_code")
    return HttpExchange(
        request=HttpRequest(
            method=str(request.get("method") or entry.method),
            url=str(request.get("url") or entry.url),
            headers=request.get("headers"),
            params=request.get("params"),
            body=request.get("body"),
        ),
        response=None
        if status_code is None
        else HttpResponse(
            status_code=int(status_code),
            headers=response.get("headers"),
            body=response.get("body"),
            duration_ms=entry.duration_ms or response.get("elapsed_ms") or 0.0,
        ),
        error=_to_error(entry.error),
        context=entry.context,
        started_at=datetime.fromisoformat(entry.started_at) if entry.started_at else None,
    )


def _to_error(error: dict[str, Any] | None) -> str | None:
    """The transport failure, as the exception it was: ``ConnectTimeout: ...``."""
    if not error:
        return None
    return f"{error.get('type') or 'Error'}: {error.get('message') or ''}".strip()

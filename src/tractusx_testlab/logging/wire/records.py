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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.


"""What a run writes down about the calls it made.

A result is kept and a result is written, and they are not the same record. The
run keeps what a step declared — the ``request`` / ``response`` it named, which a
``returns:`` block may read and assertions evaluate. What is written to the
transcript, the SSE stream and the trace is what happened on the wire, with the
credentials taken out.
"""

from __future__ import annotations

from typing import Any

from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.logging.wire.redaction import (
    SECRET_HEADERS,
    redact_secrets,
    secret_headers,
)
from tractusx_testlab.models.runtime.results import HttpRequest, HttpResponse

__all__ = ["SECRET_HEADERS", "as_recorded", "safe_headers"]


def as_recorded(result: Any) -> Any:
    """The step result as it is written down — the calls that were really made.

    What a run *keeps* and what a run *writes* are not the same record, in two
    ways:

    * A step names its own ``request`` / ``response``, and a step driving the SDK
      writes that summary itself — the URL its client would have used, its own
      parameters as the body, a ``200`` it inferred from not having raised. The
      written record carries the call the SDK actually made instead: a trace read
      to debug a SUT is worth nothing while it describes a request nobody sent.
      The last recorded call is the one it carries, which is the call the step
      was doing when it returned, and the call that failed when it did not.
    * A credential the step was handed — the EDR token, a bearer a test set —
      never went through the tracer, so it is masked here.

    Whichever account is written, it is redacted the same way — headers by name,
    bodies and the step's resolved inputs by key (logging.wire.redaction) — so a
    step that took care to redact its own request (``security/oauth2/*``) is not
    undone by the call the tracer recorded underneath it.

    The result the run keeps is untouched. Its ``request`` / ``response`` are
    what a ``returns:`` block may name and what assertions read, so they stay as
    the step declared them, headers and all; a step that made no call at all
    keeps them in the record too, because then its own account is the only one
    there is.
    """
    subject = result.exchanges[-1] if result.exchanges else None
    request = subject.request if subject is not None else result.request
    response = subject.response if subject is not None else result.response
    return result.model_copy(
        update={
            "request": _safe_request(request),
            "response": _safe_response(response),
            "inputs": redact_secrets(result.inputs),
            "exchanges": [_safe_exchange(exchange) for exchange in result.exchanges],
        }
    )


def _safe_exchange(exchange: Any) -> Any:
    return exchange.model_copy(
        update={
            "request": _safe_request(exchange.request),
            "response": _safe_response(exchange.response),
        }
    )


def _safe_request(request: HttpRequest | None) -> HttpRequest | None:
    if request is None:
        return request
    return request.model_copy(
        update={
            "headers": safe_headers(request.headers) if request.headers else request.headers,
            "params": redact_secrets(request.params),
            "body": redact_secrets(request.body),
        }
    )


def _safe_response(response: HttpResponse | None) -> HttpResponse | None:
    if response is None:
        return response
    return response.model_copy(
        update={
            "headers": safe_headers(response.headers) if response.headers else response.headers,
            "body": redact_secrets(response.body),
        }
    )


def safe_headers(headers: Any) -> dict[str, str]:
    """Header pairs with every credential replaced by the tracer's marker.

    Redaction is by name rather than by value pattern: a header named
    ``Authorization`` is a secret whatever it happens to contain, and guessing
    at shapes is how a token ends up in a file. The list and the marker are the
    ones the tracer uses, so both records read the same.
    """
    if not headers:
        return {}
    try:
        pairs = headers.items()
    except AttributeError:
        return {}
    redacted = secret_headers()
    return {
        str(name): (REDACTED_VALUE if str(name).lower() in redacted else str(value))
        for name, value in pairs
    }

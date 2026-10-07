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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from tractusx_sdk.dataspace.tools.tracing import REDACTED_VALUE

from tractusx_testlab.logging.masking import mask_also
from tractusx_testlab.logging.wire.redaction import (
    SECRET_HEADERS,
    is_secret_header,
    is_secret_key,
    redact_secrets,
    redact_url,
    written,
)
from tractusx_testlab.models.runtime.results import HttpRequest, HttpResponse, TckResult

if TYPE_CHECKING:
    from tractusx_testlab.models.runtime.results import AssertionResult, StepResult

__all__ = ["SECRET_HEADERS", "Disclosure", "as_kept", "as_recorded", "disclose", "safe_headers"]


@dataclass(frozen=True, slots=True)
class Disclosure:
    """What a step's own record shows and hides beyond the names in it.

    ``shown`` are the outputs its author revealed (``hidden: false`` on an output
    the step lets them show): not redacted for the name they are returned under.
    ``withheld`` are values the author hid that the run could not register
    (logging.masking caps how many one run pins): no other record knows them, so
    this one masks them by value.
    """

    shown: frozenset[str] = frozenset()
    withheld: tuple[str, ...] = ()


def disclose(result: StepResult, disclosure: Disclosure) -> StepResult:
    """Attach *disclosure* to the step result it was decided for, and return it."""
    result._disclosure = disclosure
    return result


def _disclosure_of(result: Any) -> Disclosure:
    disclosure = getattr(result, "_disclosure", None)
    return disclosure if isinstance(disclosure, Disclosure) else Disclosure()


def as_recorded(result: StepResult) -> StepResult:
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
    URLs by their query, bodies, the step's resolved inputs, what it returned and
    what its checks compared by key (logging.wire.redaction) — so a step that
    took care to redact its own request (``security/oauth2/*``) is not undone by
    the call the tracer recorded underneath it.

    The result the run keeps is untouched. Its ``request`` / ``response`` are
    what a ``returns:`` block may name and what assertions read, so they stay as
    the step declared them, headers and all; a step that made no call at all
    keeps them in the record too, because then its own account is the only one
    there is.
    """
    disclosure = _disclosure_of(result)
    subject = result.exchanges[-1] if result.exchanges else None
    request = subject.request if subject is not None else result.request
    response = subject.response if subject is not None else result.response
    return result.model_copy(
        update={
            "request": _safe_request(request),
            "response": _safe_response(response),
            "inputs": redact_secrets(result.inputs),
            "output": _withheld(_safe_output(result.output, disclosure.shown), disclosure),
            "assertions": [_safe_check(check, disclosure) for check in result.assertions],
            "exchanges": [_safe_exchange(exchange) for exchange in result.exchanges],
        }
    )


def as_kept(result: TckResult) -> TckResult:
    """A run's verdict as its job keeps it once the run is over.

    A job outlives its run: whoever asks for it later is shown it as any record
    is shown (logging.wire.redaction), but by then the run's secrets are no
    longer pinned and newer ones may have evicted them. So the job keeps a copy
    masked at the end of the run, while they still are. Each step keeps the
    exchange it declared — the shape the job always had.
    """
    tests = [
        test.model_copy(update={"execution": [_kept_step(step) for step in test.execution]})
        for test in result.tests
    ]
    kept = written(
        result.model_copy(update={"tests": tests}).model_dump(mode="json", by_alias=True)
    )
    try:
        return TckResult.model_validate(kept)
    except ValidationError:
        # A number masked as ``***`` no longer fits its field: kept as written.
        return TckResult.model_construct(**kept)


def _kept_step(step: StepResult) -> StepResult:
    disclosure = _disclosure_of(step)
    return step.model_copy(
        update={
            "output": _withheld(step.output, disclosure),
            "assertions": [_safe_check(check, disclosure) for check in step.assertions],
        }
    )


def _withheld(value: Any, disclosure: Disclosure) -> Any:
    return mask_also(value, list(disclosure.withheld)) if disclosure.withheld else value


def _safe_output(output: Any, shown: frozenset[str]) -> Any:
    """What the step returned, by key — but not the outputs its author revealed.

    A revealed output keeps its value; a credential nested inside it is still
    redacted, as ``hide_secrets`` still masks one.
    """
    redacted = redact_secrets(output)
    if not shown or not isinstance(output, dict):
        return redacted
    return {**redacted, **{name: redact_secrets(output[name]) for name in shown if name in output}}


def _safe_check(check: AssertionResult, disclosure: Disclosure) -> AssertionResult:
    """A check's ``expected`` and ``actual``, redacted as the field they compared is.

    A check reading ``access_token`` compares a credential whatever it is called
    in the comparison, so both sides are redacted by the name of the field the
    check read; a document compared whole is redacted by its own keys.
    """
    params = check.assertion.with_ or {}
    field = str(params.get("path") or params.get("input") or "")
    secret = bool(field) and is_secret_key(field)
    return check.model_copy(
        update={
            "expected": _withheld(_compared(check.expected, secret), disclosure),
            "actual": _withheld(_compared(check.actual, secret), disclosure),
        }
    )


def _compared(value: Any, secret: bool) -> Any:
    if secret and value not in (None, "") and not isinstance(value, bool):
        return REDACTED_VALUE
    return redact_secrets(value)


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
            "url": redact_url(request.url),
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
    at shapes is how a token ends up in a file. A name that mentions a token, a
    key or a session is one too (logging.wire.secret_names), so a proxy's
    ``X-Forwarded-Access-Token`` is redacted with the rest.
    """
    if not headers:
        return {}
    try:
        pairs = headers.items()
    except AttributeError:
        return {}
    return {
        str(name): (REDACTED_VALUE if is_secret_header(name) else str(value))
        for name, value in pairs
    }

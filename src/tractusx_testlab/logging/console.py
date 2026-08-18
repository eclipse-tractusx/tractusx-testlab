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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Turning an execution event into one line a person can read.

The engine publishes typed events — ``StepStartedEvent``, ``AssertionResultEvent``,
``StepCompletedEvent`` — and writes every field of them to the JSONL that the
IDE and the report parse. This module is the other audience: someone watching a
run go by, who needs to see which step is running, what each check asked and
answered, and what went over the wire, without reading JSON.
"""

from __future__ import annotations

import json

from tractusx_testlab.models.primitives.enums import EventKind

#: The three ways a step can finish. All three render the same columns —
#: which step, what came of it, how long — so a failure is not a different
#: shape from a pass and both are scannable in one pass down the log.
_STEP_OUTCOME_KINDS: frozenset[str] = frozenset(
    {
        EventKind.STEP_COMPLETED.value,
        EventKind.STEP_FAILED.value,
        EventKind.STEP_SKIPPED.value,
    }
)

#: Longest wire body echoed to the console. The JSONL keeps the whole thing;
#: a console line that wraps four times is not a trace anyone reads.
_MAX_BODY = 240


def _clip(value: object, limit: int = _MAX_BODY) -> str:
    """Render *value* compactly, cut to *limit* with the cut made visible."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else f"{text[:limit]}…(+{len(text) - limit})"


def _where(data: dict) -> str:
    """The script and step a line is about, as one column."""
    script = data.get("script") or ""
    step = data.get("step_id") or ""
    result = data.get("result") or {}
    if not step and isinstance(result, dict):
        step = result.get("step_name") or ""
    return f"[{script}]{' ' + step if step else ''}"


def _assertion_line(data: dict) -> str:
    """One evaluated check: what it asked, and what it saw.

    The verdict comes first so a failure is findable by eye in a long run.
    """
    entry = data.get("assertion") or {}
    declared = entry.get("assertion") or {}
    params = declared.get("with_") or declared.get("with") or {}
    operator = params.get("operator") or str(declared.get("uses", "")).rsplit("/", 1)[-1]
    subject = params.get("input") or "<output>"
    if params.get("path"):
        subject = f"{subject}.{params['path']}"

    verdict = "assert.pass" if entry.get("passed") else "assert.FAIL"
    parts = [verdict, _where(data), f"#{data.get('index', 0)}", f"{operator}({subject})"]
    if entry.get("expected") is not None:
        parts.append(f"expected={_clip(entry['expected'], 80)}")
    parts.append(f"actual={_clip(entry.get('actual'), 80)}")
    if not entry.get("passed") and entry.get("message"):
        parts.append(f"— {entry['message']}")
    if entry.get("severity") and entry["severity"] != "HARD":
        parts.append(f"({entry['severity'].lower()})")
    return " ".join(parts)


def _exchange_lines(result: dict) -> list[str]:
    """The request a step sent and the answer it got, when it made one.

    A step that talks to the SUT is the only place a conformance verdict comes
    from, so the wire is part of the trace rather than something to reconstruct
    from the JSONL afterwards.
    """
    lines: list[str] = []
    request = result.get("request")
    if request:
        line = f"  → {request.get('method', '?')} {request.get('url', '?')}"
        if request.get("body") is not None:
            line += f" body={_clip(request['body'])}"
        lines.append(line)
    response = result.get("response")
    if response:
        line = f"  ← {response.get('status_code', '?')}"
        # Only when something measured it. The field defaults to 0.0, and a
        # printed "in 0ms" reads as a measurement rather than as its absence.
        if response.get("duration_ms"):
            line += f" in {float(response['duration_ms']):.0f}ms"
        if response.get("body") is not None:
            line += f" body={_clip(response['body'])}"
        lines.append(line)
    return lines


def _step_outcome_line(base: str, data: dict) -> str:
    """A finished step: which one, what came of it, and how long it took."""
    result = data.get("result") or {}
    parts = [base, _where(data), str(result.get("step_type", ""))]
    status = result.get("status")
    if status:
        parts.append(str(status))
    duration = result.get("duration_s")
    if duration is not None:
        parts.append(f"{float(duration) * 1000:.0f}ms")
    if result.get("error"):
        parts.append(f"— {result['error']}")
    line = " ".join(p for p in parts if p)
    exchange = _exchange_lines(result)
    return "\n".join([line, *exchange]) if exchange else line


def render(base_msg: str, extra_data: dict[str, object]) -> str:
    """Render an execution event as one readable console line.

    This used to look for flat ``status`` / ``duration_s`` / ``request`` /
    ``response`` keys. Events carry a nested ``result`` (a ``StepResult``)
    and a nested ``assertion`` instead, so none of those keys were ever
    present and every step and assertion line printed as its bare event name
    and the script it belonged to — ``assertion.result [wiring]``, which
    says neither which check ran nor whether it passed. The JSONL had the
    whole story the entire time; only the console threw it away.
    """
    kind = str(extra_data.get("kind", ""))

    if kind == EventKind.ASSERTION_RESULT.value:
        return _assertion_line(extra_data)

    if kind in _STEP_OUTCOME_KINDS:
        return _step_outcome_line(base_msg, extra_data)

    if kind == EventKind.STEP_STARTED.value:
        return " ".join(
            part
            for part in (
                base_msg,
                _where(extra_data),
                str(extra_data.get("step_type", "")),
                f"({extra_data['phase']})" if extra_data.get("phase") else "",
            )
            if part
        )

    if kind == EventKind.SCRIPT_COMPLETED.value:
        result = extra_data.get("result")
        if not isinstance(result, dict):
            result = {}
        summary = result.get("assertion_summary") or {}
        status = result.get("status", "")
        checks = (
            f"{summary.get('passed', 0)}/{summary.get('total', 0)} checks passed" if summary else ""
        )
        return " ".join(
            part
            for part in (base_msg, f"[{result.get('script_name', '')}]", str(status), checks)
            if part
        )

    parts: list[str] = [base_msg]
    for key in ("tck_id", "tck", "script", "package", "checksum", "status", "error"):
        if extra_data.get(key):
            parts.append(f"[{extra_data[key]}]")
    return " ".join(parts)

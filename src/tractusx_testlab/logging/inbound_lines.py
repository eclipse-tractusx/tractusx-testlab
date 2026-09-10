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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""The console lines for an inbound call: where to call, and what arrived.

Everything else on the console is testlab calling out. These three lines are
for the moments the run depends on a call coming *in* — and they are written
for the person who may have to make it by hand: the address leads, and it is
the address exactly as the step published it.
"""

from __future__ import annotations

import json

#: Longest inbound body echoed on the received line; the trace has the whole one.
_MAX_BODY = 80


def _where(data: dict) -> str:
    script = data.get("script") or ""
    step = data.get("step_id") or ""
    return f"[{script}]{' ' + step if step else ''}"


def _call(data: dict) -> str:
    listener = data.get("listener") or {}
    return f"— call {listener.get('method', '?')} {listener.get('url', '?')}"


def listening_line(base: str, data: dict) -> str:
    """``mock/api`` opened an address: from now on, this is where to call."""
    return " ".join(
        p for p in (base, _where(data), str(data.get("step_type", "")), _call(data)) if p
    )


def waiting_line(base: str, data: dict) -> str:
    """The run is blocked on the address, and this is how long it will wait."""
    timeout = data.get("timeout_s")
    budget = f"(up to {float(timeout):.0f}s)" if timeout else ""
    parts = (base, _where(data), str(data.get("step_type", "")), _call(data), budget)
    return " ".join(p for p in parts if p)


def received_line(base: str, data: dict) -> str:
    """The call arrived: what came in, and how long the step had been waiting."""
    request = data.get("request") or {}
    parts = [base, _where(data), str(data.get("step_type", ""))]
    parts.append(f"← {request.get('method', '?')} {request.get('path', '?')}")
    parts.append(f"after {int(data.get('waited_ms') or 0)}ms")
    payload = request.get("payload")
    if payload is not None:
        text = payload if isinstance(payload, str) else json.dumps(payload, default=str)
        clipped = (
            text if len(text) <= _MAX_BODY else f"{text[:_MAX_BODY]}…(+{len(text) - _MAX_BODY})"
        )
        parts.append(f"body={clipped}")
    return " ".join(p for p in parts if p)

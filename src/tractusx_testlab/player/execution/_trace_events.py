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

"""Turning the engine's typed events into the ADR-0016 trace vocabulary.

The engine's own events are named for what the runtime does — a *job* runs
*scripts* made of *steps*. The trace is named for what a reader is looking at —
a *TCK* runs *tests* made of *steps*. This module is the single place the two
vocabularies meet, so neither has to be renamed to satisfy the other and the
mapping is one file to read rather than a rule to infer from call sites.

It also does the one reshaping ADR-0016 requires: assertions are *not* separate
events, they are ``data.validations[]`` inside the step's terminal event, so a
step result is self-contained for whoever renders it.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.models.primitives.enums import ScriptStatus, StepStatus
from tractusx_testlab.models.runtime.results import (
    ENGINE_FAULT_PREFIX,
    AssertionResult,
    ScriptResult,
    StepResult,
)

#: Step outcome -> trace event type.
_STEP_TYPES: dict[StepStatus, str] = {
    StepStatus.PASSED: "tck.test.step.passed",
    StepStatus.FAILED: "tck.test.step.failed",
    StepStatus.SKIPPED: "tck.test.step.skipped",
}

#: Test outcome -> trace event type.
_TEST_TYPES: dict[ScriptStatus, str] = {
    ScriptStatus.COMPLETED: "tck.test.passed",
    ScriptStatus.FAILED: "tck.test.failed",
    ScriptStatus.SKIPPED: "tck.test.skipped",
    ScriptStatus.CANCELLED: "tck.test.skipped",
}


def step_event_type(status: StepStatus) -> str:
    """The trace type a step outcome is published under."""
    return _STEP_TYPES.get(status, "tck.test.step.failed")


def test_event_type(status: ScriptStatus) -> str:
    """The trace type a test outcome is published under."""
    return _TEST_TYPES.get(status, "tck.test.failed")


def validation_of(result: AssertionResult) -> dict[str, Any]:
    """One evaluated check, in the nested shape ADR-0016 defines.

    ``field`` names what was checked rather than repeating the whole assertion:
    the reader wants to know which output disagreed, and ``input`` plus ``path``
    is where a script says so.
    """
    declared = result.assertion
    params = declared.with_ or {}
    field = str(params.get("input") or "")
    if params.get("path"):
        field = f"{field}.{params['path']}" if field else str(params["path"])

    inputs: dict[str, Any] = {
        "assertion": params.get("operator") or str(declared.uses).rsplit("/", 1)[-1]
    }
    if result.expected is not None:
        inputs["expected"] = result.expected

    validation: dict[str, Any] = {
        "source": declared.uses,
        "field": field,
        "inputs": inputs,
        "outputs": {"actual": result.actual, "passed": result.passed},
    }
    if not result.passed:
        validation["errors"] = [
            {
                "code": "ASSERTION_FAILED",
                "message": result.message or f"{inputs['assertion']} did not hold for '{field}'",
                "severity": result.severity.value,
                "retryable": False,
            }
        ]
    return validation


def _errors_of(result: StepResult) -> list[dict[str, Any]]:
    """The step's own failure, separated from the checks that merely disagreed.

    An engine fault is not a verdict about the SUT, so it keeps its own code:
    a reader triaging a red run needs to know whether to fix the SUT or file a
    bug against TestLab, and one ``FAILED`` cannot say which.

    A failure that named itself keeps its own name — ``POLICY_MISMATCH`` rather
    than a second ``STEP_FAILED`` — and its ``context`` carries the evidence the
    message describes, so the IDE renders the comparison instead of parsing a
    paragraph back into one.
    """
    errors: list[dict[str, Any]] = []
    if result.error:
        engine_fault = result.error.startswith(ENGINE_FAULT_PREFIX)
        error: dict[str, Any] = {
            "code": result.error_code or ("ENGINE_FAULT" if engine_fault else "STEP_FAILED"),
            "message": result.error.removeprefix(ENGINE_FAULT_PREFIX),
            "retryable": False,
            "origin": "engine" if engine_fault else "sut",
        }
        if result.error_context:
            error["context"] = result.error_context
        errors.append(error)
    return errors


#: What a script calls a step's whole output when the step publishes one bare
#: value instead of named fields. ``util/base64`` and ``util/json_path_extract``
#: are read as ``${{ execution.<step>.value }}`` and declare ``returns: value:``,
#: so ``value`` is the name that output already has everywhere else — it is in
#: ``UNIVERSAL_RETURNS``, and it is what the trace has to agree with.
_BARE_OUTPUT_NAME = "value"


def _outputs_of(result: StepResult) -> Any:
    """What the step published, under the names a script reads it by.

    A step with named outputs publishes a mapping — ``dataplane_url``,
    ``edr_token`` — and the trace carried it as one. A step whose whole output
    is a single value published the value naked, so the trace held a bare string
    with nothing saying which output it was: readable only for a step that has
    exactly one, and unreadable next to a step that has several. The bare value
    is named here, so ``data.outputs`` is a mapping of output name to value for
    every step, and the name is the same one the script wrote in ``returns:``.

    ``None`` stays ``None``: a step that produced nothing published no name
    either, and ``{"value": null}`` would claim one.
    """
    if result.output is None or isinstance(result.output, dict):
        return result.output
    return {_BARE_OUTPUT_NAME: result.output}


def step_data(result: StepResult, *, attempt: int = 1) -> dict[str, Any]:
    """The ``data`` of a terminal step event.

    What went in and what came out, with the verdict: ``inputs`` is the ``with:``
    block as it resolved, ``outputs`` is what the step published, ``validations``
    are the checks it was measured by.

    The wire is **not** here. Every call was already published as it happened
    (``tck.test.step.call``), in order, in the same stream — repeating the whole
    conversation in the terminal event would put a 1.6 kB catalog answer in the
    trace twice, and a 64-call poll loop sixty-five times.
    """
    data: dict[str, Any] = {
        "attempt": attempt,
        "duration_ms": round((result.duration_s or 0.0) * 1000, 3),
        "outputs": _outputs_of(result),
        "validations": [validation_of(item) for item in result.assertions],
    }
    if result.inputs:
        data["inputs"] = result.inputs
    errors = _errors_of(result)
    if errors:
        data["errors"] = errors
    return data


def call_data(index: int, call: Any) -> dict[str, Any]:
    """One call, as the trace carries it.

    ``context`` names who made it — the SDK method for a call the SDK made on the
    engine's behalf, ``testlab/http_client`` for one the engine made itself — so
    a reader of a long conversation can tell the layers apart without inferring
    them from the URL.
    """
    data: dict[str, Any] = {
        "index": index,
        "context": call.context,
        "started_at": call.started_at,
        "request": call.request,
    }
    if call.response is not None:
        data["response"] = call.response
    if call.error:
        data["errors"] = [{"code": "TRANSPORT_FAILED", "message": call.error, "retryable": True}]
    return data


def test_data(result: ScriptResult) -> dict[str, Any]:
    """The ``data`` of a terminal test event."""
    summary = result.assertion_summary
    data: dict[str, Any] = {
        "test_id": result.script_id or result.script_name,
        "duration_ms": round((result.total_duration_s or 0.0) * 1000, 3),
        "assertions": {
            "declared": summary.declared,
            "total": summary.total,
            "passed": summary.passed,
            "failed_hard": summary.failed_hard,
            "failed_soft": summary.failed_soft,
        }
        if summary
        else {},
    }
    if summary:
        data["passed"] = summary.passed
        data["failed"] = summary.failed_hard + summary.failed_soft
    if result.error:
        data["errors"] = [{"code": "TEST_FAILED", "message": result.error, "retryable": False}]
    return data

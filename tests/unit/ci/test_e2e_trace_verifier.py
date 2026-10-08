###############################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
###############################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: GPT-5.6 Sol).
## It was reviewed and tested by a human committer.

"""Execute the workflow's inbound trace verifier against real trace envelopes."""

from pathlib import Path

import pytest
import yaml

from tests.paths import REPO_ROOT
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models.primitives.enums import StepPhase, StepStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.player.execution._trace_publisher import TracePublisher

_WORKFLOW = REPO_ROOT / ".github/workflows/e2e-umbrella.yml"
_TCK = "testlab-e2e-connector-dtr-smoke"
_RUN = "callback-run"
# Deliberately not derivable from the BPN or run id.
_ASSET = "another-engine:arbitrary-scope:returned-asset"


@pytest.fixture
def verifier(tmp_path: Path) -> str:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    (step,) = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if step.get("name") == "Verify the inbound calls in the execution trace"
    ]
    shell = step["run"]
    opener = "poetry run python - <<'PY'\n"
    assert shell.startswith(opener) and shell.endswith("PY\n")
    script = shell[len(opener) : -len("PY\n")]
    # Only redirect the trace directory; execute the entire shipped verifier.
    assert script.count('pathlib.Path("/data")') == 1
    return script.replace('pathlib.Path("/data")', f"pathlib.Path({str(tmp_path)!r})")


def _verify(script: str) -> None:
    exec(compile(script, str(_WORKFLOW), "exec"), {"__name__": "__main__"})


def _write_trace(
    path: Path,
    outputs: dict | None,
    *,
    run_id: str = _RUN,
    offered_id: str = _ASSET,
    filter_id: str = _ASSET,
    creation_count: int = 1,
    callback_run: str | None = _RUN,
) -> None:
    trace = ExecutionTrace(_TCK, path)
    publisher = TracePublisher(trace)
    try:
        publisher.run_started(run_id, _TCK)
        for _ in range(creation_count):
            publisher.step_ended(
                "dataplane-callback",
                "create_asset",
                StepResult(
                    step_name="create_asset",
                    step_type="connector/provider/create_mock_asset",
                    phase=StepPhase.SETUP,
                    status=StepStatus.PASSED,
                    output=outputs,
                ),
            )
        delivered = [
            ("inbound-call", "await_call", "GET", None, 0),
            (
                "inbound-call",
                "await_notification",
                "POST",
                {"header": {"messageId": "urn:uuid:testlab-e2e-inbound-notification"}},
                0,
            ),
            ("inbound-call", "await_question", "POST", {"content": {"question": "ping"}}, 0),
            ("external-callback", "await_call", "POST", {"from": "stub-sut"}, 3000),
            ("dataplane-callback", "await_callback", "POST", {"run": callback_run}, 0),
            (
                "notification-roundtrip",
                "await_notification",
                "POST",
                {"header": {"messageId": "notification", "senderBpn": "a", "receiverBpn": "b"}},
                0,
            ),
            (
                "notification-roundtrip",
                "await_direct_notification",
                "POST",
                {"header": {"messageId": "notification", "senderBpn": "a", "receiverBpn": "b"}},
                0,
            ),
            ("push-transfer", "await_push", "POST", None, 0),
        ]
        for test, step, method, body, waited_ms in delivered:
            trace.emit(
                "tck.test.step.received",
                {"request": {"method": method, "body": body}, "waited_ms": waited_ms},
                scope=(test, "execution", step),
            )
        trace.emit(
            "tck.test.step.waiting",
            {"listener": {"via": "direct"}},
            scope=("inbound-call", "execution", "await_call"),
        )
        trace.emit(
            "tck.test.step.waiting",
            {
                "listener": {
                    "via": "dataplane",
                    "offer": {
                        "asset_id": offered_id,
                        "dsp_url": "http://consumer-dsp.local/api/v1/dsp/2025-1",
                        "participant_id": "did:web:consumer.local:identityhub:BPNL000000000002",
                        "properties": {},
                        "catalog_filters": [
                            {
                                "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                                "operator": "=",
                                "operandRight": filter_id,
                            }
                        ],
                    },
                }
            },
            scope=("dataplane-callback", "execution", "await_callback"),
        )
    finally:
        trace.close()


def test_verifier_accepts_arbitrary_returned_scoped_asset(verifier: str, tmp_path: Path) -> None:
    _write_trace(tmp_path / "current.jsonl", {"asset_id": _ASSET})

    _verify(verifier)


@pytest.mark.parametrize(
    "offer", [{"offered_id": "different-asset"}, {"filter_id": "different-asset"}]
)
def test_verifier_rejects_mismatched_offer_or_filter(
    verifier: str, tmp_path: Path, offer: dict[str, str]
) -> None:
    _write_trace(
        tmp_path / "current.jsonl",
        {"asset_id": _ASSET},
        offered_id=offer.get("offered_id", _ASSET),
        filter_id=offer.get("filter_id", _ASSET),
    )

    with pytest.raises(SystemExit, match="the wait announced"):
        _verify(verifier)


def test_verifier_rejects_missing_creation(verifier: str, tmp_path: Path) -> None:
    _write_trace(tmp_path / "current.jsonl", None, creation_count=0)

    with pytest.raises(SystemExit, match="successful setup create_asset.*found 0"):
        _verify(verifier)


@pytest.mark.parametrize("outputs", [None, {}, {"asset_id": None}, {"asset_id": ""}])
def test_verifier_rejects_missing_or_null_asset_output(
    verifier: str, tmp_path: Path, outputs: dict | None
) -> None:
    _write_trace(tmp_path / "current.jsonl", outputs)

    with pytest.raises(SystemExit, match="returned no asset_id"):
        _verify(verifier)


def test_verifier_does_not_use_previous_runs_creation(verifier: str, tmp_path: Path) -> None:
    _write_trace(
        tmp_path / "a-previous.jsonl",
        {"asset_id": _ASSET},
        run_id="previous",
        callback_run="previous",
    )
    _write_trace(tmp_path / "b-current.jsonl", None, creation_count=0)

    with pytest.raises(SystemExit, match="successful setup create_asset.*found 0"):
        _verify(verifier)


def test_verifier_uses_current_creation_not_previous_output(verifier: str, tmp_path: Path) -> None:
    _write_trace(
        tmp_path / "a-previous.jsonl",
        {"asset_id": "old-asset"},
        run_id="previous",
        callback_run="previous",
    )
    _write_trace(tmp_path / "b-current.jsonl", {"asset_id": _ASSET})

    _verify(verifier)


def test_verifier_rejects_ambiguous_creations(verifier: str, tmp_path: Path) -> None:
    _write_trace(tmp_path / "current.jsonl", {"asset_id": _ASSET}, creation_count=2)

    with pytest.raises(SystemExit, match="successful setup create_asset.*found 2"):
        _verify(verifier)


def test_verifier_rejects_ambiguous_run_traces(verifier: str, tmp_path: Path) -> None:
    for name in ("a.jsonl", "b.jsonl"):
        _write_trace(tmp_path / name, {"asset_id": _ASSET})

    with pytest.raises(SystemExit, match="one trace for callback run.*found 2"):
        _verify(verifier)


def test_verifier_rejects_callback_without_run_id(verifier: str, tmp_path: Path) -> None:
    _write_trace(tmp_path / "current.jsonl", {"asset_id": _ASSET}, callback_run=None)

    with pytest.raises(SystemExit, match="callback did not carry the run id"):
        _verify(verifier)


def test_verifier_rejects_callback_from_different_run(verifier: str, tmp_path: Path) -> None:
    _write_trace(tmp_path / "current.jsonl", {"asset_id": _ASSET}, run_id="different-run")

    with pytest.raises(SystemExit, match="one trace for callback run.*found 0"):
        _verify(verifier)

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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""The workflow's API-file verifier, run against traces the player's own publisher writes.

``Verify the API files and auth steps in the execution trace`` is what fails
``e2e-umbrella.yml`` when ``env.apis`` or the two auth steps did not run or did
not pass, or when a step copied an API file into the trace. The script is taken
out of the workflow as shipped and run whole; only the trace directory moves.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.paths import REPO_ROOT
from tractusx_testlab.logging import wire
from tractusx_testlab.logging.masking import forget_secrets
from tractusx_testlab.logging.trace import ExecutionTrace
from tractusx_testlab.models.primitives.enums import StepPhase, StepStatus
from tractusx_testlab.models.runtime.results import StepResult
from tractusx_testlab.openapi import BoundApiDocument, forget_api_documents, load_api_document
from tractusx_testlab.player.execution._trace_publisher import TracePublisher

_WORKFLOW = REPO_ROOT / ".github/workflows/e2e-umbrella.yml"
_E2E = REPO_ROOT / "tests/e2e/connector-dtr-smoke"
_TCK = "testlab-e2e-connector-dtr-smoke"
_STEP = "Verify the API files and auth steps in the execution trace"

_API_FILES = ("dtr_profile", "dtr_description", "mock_key_header", "mock_key", "call_echo")
_TOOLBOX = ("mock_key", "call_with_key", "basic_auth", "call_with_basic")


def _workflow_steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


@pytest.fixture
def verifier(tmp_path: Path) -> str:
    (step,) = [step for step in _workflow_steps() if step.get("name") == _STEP]
    shell = step["run"]
    opener = "poetry run python - <<'PY'\n"
    assert shell.startswith(opener) and shell.endswith("PY\n")
    script = shell[len(opener) : -len("PY\n")]
    assert script.count('pathlib.Path("/data")') == 1
    return script.replace('pathlib.Path("/data")', f"pathlib.Path({str(tmp_path)!r})")


@pytest.fixture(autouse=True)
def _fresh() -> Any:
    forget_api_documents()
    forget_secrets()
    yield
    forget_api_documents()
    forget_secrets()


def _verify(script: str) -> None:
    exec(compile(script, str(_WORKFLOW), "exec"), {"__name__": "__main__"})


def _documents() -> dict[str, Any]:
    """Both API files as a run binds them: read-only, under the id the manifest gives."""
    apis = _E2E / "apis"
    files = {
        "dtr": ("aas-registry-openapi.yaml", "application/vnd.oai.openapi"),
        "testlab_mock": ("testlab-mock.json", "application/vnd.oai.openapi+json"),
    }
    bound = {}
    for api_id, (source, media_type) in files.items():
        loaded = load_api_document(apis / source, media_type)
        bound[api_id] = BoundApiDocument(loaded.content, api_id, loaded.sha256)
    return bound


def _write_trace(
    path: Path,
    *,
    missing: tuple[str, str] | None = None,
    failed: tuple[str, str] | None = None,
    twice: tuple[str, str] | None = None,
    whole_document: bool = False,
) -> None:
    """A full run's trace for the two tests, written as the monitor writes it."""
    documents = _documents()
    handed = {"dtr_profile": "dtr", "mock_key_header": "testlab_mock"}
    trace = ExecutionTrace(_TCK, path)
    publisher = TracePublisher(trace)
    try:
        publisher.run_started("api-run", _TCK)
        for test, steps in (("api-files", _API_FILES), ("engine-toolbox", _TOOLBOX)):
            for step in steps:
                if (test, step) == missing:
                    continue
                inputs: dict[str, Any] = {"path": "x"}
                if test == "api-files" and step in handed:
                    document = documents[handed[step]]
                    inputs["input"] = dict(document) if whole_document else document
                result = StepResult(
                    step_name=step,
                    step_type="util/json_path_extract",
                    phase=StepPhase.EXECUTION,
                    status=StepStatus.FAILED if (test, step) == failed else StepStatus.PASSED,
                    inputs=inputs,
                    error="boom" if (test, step) == failed else None,
                )
                for _ in range(2 if (test, step) == twice else 1):
                    publisher.step_ended(test, step, wire.as_recorded(result))
    finally:
        trace.close()


def test_a_complete_run_passes(
    verifier: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _write_trace(tmp_path / "run.jsonl")
    _verify(verifier)
    assert "both API files recorded by summary" in capsys.readouterr().out


@pytest.mark.parametrize(
    "step",
    [*(("api-files", s) for s in _API_FILES), *(("engine-toolbox", s) for s in _TOOLBOX)],
)
def test_a_step_that_did_not_run_fails_the_job(
    verifier: str, tmp_path: Path, step: tuple[str, str]
) -> None:
    _write_trace(tmp_path / "run.jsonl", missing=step)
    with pytest.raises(SystemExit, match=f"{step[0]}: {step[1]} ended 0 times"):
        _verify(verifier)


@pytest.mark.parametrize(
    "step", [("api-files", "dtr_description"), ("engine-toolbox", "basic_auth")]
)
def test_a_step_that_failed_fails_the_job(
    verifier: str, tmp_path: Path, step: tuple[str, str]
) -> None:
    _write_trace(tmp_path / "run.jsonl", failed=step)
    with pytest.raises(SystemExit, match=f"{step[0]}: {step[1]} did not pass"):
        _verify(verifier)


def test_a_step_that_ran_twice_fails_the_job(verifier: str, tmp_path: Path) -> None:
    _write_trace(tmp_path / "run.jsonl", twice=("api-files", "call_echo"))
    with pytest.raises(SystemExit, match="call_echo ended 2 times"):
        _verify(verifier)


def test_an_api_file_copied_into_the_trace_fails_the_job(verifier: str, tmp_path: Path) -> None:
    _write_trace(tmp_path / "run.jsonl", whole_document=True)
    with pytest.raises(SystemExit, match="does not record its API file by summary"):
        _verify(verifier)


def test_a_run_without_a_trace_fails_the_job(verifier: str) -> None:
    with pytest.raises(SystemExit, match="ended 0 times"):
        _verify(verifier)


def test_the_full_suite_runs_both_tests() -> None:
    """The full run is the one the verifier reads; it may skip neither test."""
    manifest = yaml.safe_load((_E2E / "index.yaml").read_text(encoding="utf-8"))
    listed = {entry["id"] for entry in manifest["tests"]}
    assert {"api_files.yaml", "engine_toolbox.yaml"} <= listed
    (full,) = [s for s in _workflow_steps() if s.get("name") == "testlab run — full suite"]
    assert "skip_tests" not in full["run"]


@pytest.mark.parametrize(
    ("name", "kept"),
    [
        ("testlab run — registry alone", {"dtr_roundtrip.yaml"}),
        ("testlab run — engine toolbox alone", {"engine_toolbox.yaml"}),
    ],
)
def test_a_subset_run_skips_every_other_test(name: str, kept: set[str]) -> None:
    """A test added to the manifest must be added to each subset run's skip list."""
    manifest = yaml.safe_load((_E2E / "index.yaml").read_text(encoding="utf-8"))
    listed = {entry["id"] for entry in manifest["tests"]}
    (run,) = [s for s in _workflow_steps() if s.get("name") == name]
    skipped = set(re.search(r"skip_tests=([^\"]+)\"", run["run"]).group(1).split(","))  # type: ignore[union-attr]
    assert listed - skipped == kept
